# Copyright 2013 Joel Dunham
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Contains the :class:`PhonologiesController` and its auxiliary functions.

.. module:: phonologies
   :synopsis: Contains the phonologies controller and its auxiliary functions.

"""

import logging
import datetime
import re
import simplejson as json
import os
import codecs
from subprocess import call, PIPE, Popen
from shutil import rmtree
from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import PhonologySchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Phonology
from onlinelinguisticdatabase.lib.worker import worker_q

log = logging.getLogger(__name__)

class PhonologiesController(BaseController):
    """Generate responses to requests on phonology resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder('Phonology', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all phonology resources.

        :URL: ``GET /phonologies`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all phonology resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerloadPhonology(Session.query(Phonology))
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """Create a new phonology resource and return it.

        :URL: ``POST /phonologies``
        :request body: JSON object representing the phonology to create.
        :returns: the newly created phonology.

        """
        try:
            schema = PhonologySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            phonology = createNewPhonology(data)
            Session.add(phonology)
            Session.commit()
            savePhonologyScript(phonology)
            return phonology
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """Return the data necessary to create a new phonology.

        :URL: ``GET /phonologies/new``.
        :returns: an empty dictionary.

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a phonology and return it.
        
        :URL: ``PUT /phonologies/id``
        :Request body: JSON object representing the phonology with updated attribute values.
        :param str id: the ``id`` value of the phonology to be updated.
        :returns: the updated phonology model.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(int(id))
        if phonology:
            try:
                schema = PhonologySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                phonology = updatePhonology(phonology, data)
                # phonology will be False if there are no changes (cf. updatePhonology).
                if phonology:
                    Session.add(phonology)
                    Session.commit()
                    savePhonologyScript(phonology)
                    return phonology
                else:
                    response.status_int = 400
                    return {'error':
                        u'The update request failed because the submitted data were not new.'}
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing phonology and return it.

        :URL: ``DELETE /phonologies/id``
        :param str id: the ``id`` value of the phonology to be deleted.
        :returns: the deleted phonology model.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(id)
        if phonology:
            Session.delete(phonology)
            Session.commit()
            removePhonologyDirectory(phonology)
            return phonology
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a phonology.
        
        :URL: ``GET /phonologies/id``
        :param str id: the ``id`` value of the phonology to be returned.
        :returns: a phonology model object.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(id)
        if phonology:
            return phonology
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a phonology and the data needed to update it.

        :URL: ``GET /phonologies/edit``
        :param str id: the ``id`` value of the phonology that will be updated.
        :returns: a dictionary of the form::

                {"phonology": {...}, "data": {...}}

            where the value of the ``phonology`` key is a dictionary
            representation of the phonology and the value of the ``data`` key
            is an empty dictionary.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(id)
        if phonology:
            return {'data': {}, 'phonology': phonology}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def compile(self, id):
        """Compile the script of a phonology as a foma FST.

        :URL: ``PUT /phonologies/compile/id``
        :param str id: the ``id`` value of the phonology whose script will be compiled.
        :returns: if the phonology exists and foma is installed, the phonology
            model is returned;  ``GET /phonologies/id`` must be polled to
            determine when and how the compilation task has terminated.

        .. note::

            The script is compiled asynchronously in a worker thread.  See 
            :mod:`onlinelinguisticdatabase.lib.worker`.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.fomaInstalled():
                phonologyDirPath = getPhonologyDirPath(phonology)
                worker_q.put({
                    'id': h.generateSalt(),
                    'func': 'compilePhonologyScript',
                    'args': (phonology.id, phonologyDirPath, session['user'].id,
                             h.phonologyCompileTimeout)
                })
                return phonology
            else:
                response.status_int = 400
                return {'error': 'The command-line programs foma and flookup must be installed in order to compile phonologies.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def applydown(self, id):
        """Apply-down (i.e., phonologize) the input in the request body using a phonology.

        :URL: ``PUT /phonologies/applydown/id`` (or ``PUT /phonologies/phonologize/id``)
        :param str id: the ``id`` value of the phonology that will be used.
        :returns: if the phonology exists and foma is installed, the phonology
            model is returned;  ``GET /phonologies/id`` must be polled to
            determine when and how the compilation task has terminated.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.fomaInstalled():
                phonologyBinaryPath = getPhonologyFilePath(phonology, 'binary')
                if os.path.isfile(phonologyBinaryPath):
                    inputs = json.loads(unicode(request.body, request.charset))
                    result = {}
                    for segmentation in inputs:
                        p = Popen(['flookup', '-x', '-i', phonologyBinaryPath],
                                  shell=False,
                                  stdin=PIPE,
                                  stdout=PIPE)
                        p.stdin.write(segmentation.encode('utf-8'))
                        result[segmentation] = filter(
                            None, unicode(p.communicate()[0], 'utf-8').split('\n'))
                    return result
                else:
                    response.status_int = 400
                    return {'error': 'Phonology %d has not been compiled yet.'}
            else:
                response.status_int = 400
                return {'error': 'The command-line programs foma and flookup must be installed in order to compile phonologies.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}


################################################################################
# Phonology Create & Update Functions
################################################################################

def createNewPhonology(data):
    """Create a new phonology.

    :param dict data: the data for the phonology to be created.
    :returns: an SQLAlchemy model object representing the phonology.

    """
    phonology = Phonology()
    phonology.name = h.normalize(data['name'])
    phonology.description = h.normalize(data['description'])
    phonology.script = h.normalize(data['script'])  # normalize or not?

    phonology.enterer = session['user']
    phonology.modifier = session['user']

    now = datetime.datetime.utcnow()
    phonology.datetimeModified = now
    phonology.datetimeEntered = now
    return phonology

def updatePhonology(phonology, data):
    """Update a phonology.

    :param page: the phonology model to be updated.
    :param dict data: representation of the updated phonology.
    :returns: the updated phonology model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = h.setAttr(phonology, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(phonology, 'description', h.normalize(data['description']), changed)
    changed = h.setAttr(phonology, 'script', h.normalize(data['script']), changed)

    if changed:
        phonology.modifier = session['user']
        phonology.datetimeModified = datetime.datetime.utcnow()
        return phonology
    return changed

def savePhonologyScript(phonology):
    """Save the phonology's ``script`` value to disk as ``phonology_<id>.script``.
    
    Also create the phonology compiler shell script, i.e., ``phonology_<id>.sh``
    which will be used to compile the phonology FST to a binary.

    :param phonology: a phonology model.
    :returns: the absolute path to the newly created phonology script file.

    """
    try:
        phonologyDirPath = createPhonologyDir(phonology)
        phonologyScriptPath = getPhonologyFilePath(phonology, 'script')
        phonologyBinaryPath = getPhonologyFilePath(phonology, 'binary')
        phonologyCompilerPath = getPhonologyFilePath(phonology, 'compiler')
        with codecs.open(phonologyScriptPath, 'w', 'utf8') as f:
            f.write(phonology.script)
        # The compiler shell script loads the foma script and compiles it to binary form.
        with open(phonologyCompilerPath, 'w') as f:
            f.write('#!/bin/sh\nfoma -e "source %s" -e "regex phonology;" -e "save stack %s" -e "quit"' % (
                    phonologyScriptPath, phonologyBinaryPath))
        os.chmod(phonologyCompilerPath, 0744)
        return phonologyScriptPath
    except Exception:
        return None

def createPhonologyDir(phonology):
    """Create the directory to hold the phonology script and auxiliary files.
    
    :param phonology: a phonology model object.
    :returns: an absolute path to the directory for the phonology.

    """
    phonologyDirPath = getPhonologyDirPath(phonology)
    h.makeDirectorySafely(phonologyDirPath)
    return phonologyDirPath

def getPhonologyDirPath(phonology):
    """Return the path to a phonology's directory.
    
    :param phonology: a phonology model object.
    :returns: an absolute path to the directory for the phonology.

    """
    return os.path.join(config['analysis_data'],
                                    'phonology', 'phonology_%d' % phonology.id)

def getPhonologyFilePath(phonology, fileType='script'):
    """Return the path to a phonology's file of the given type.
    
    :param phonology: a phonology model object.
    :param str fileType: one of 'script', 'binary', 'compiler', or 'tester'.
    :returns: an absolute path to the phonology's script file.

    """
    extMap = {'script': 'script', 'binary': 'foma', 'compiler': 'sh', 'tester': 'tester.sh'}
    return os.path.join(getPhonologyDirPath(phonology),
            'phonology_%d.%s' % (phonology.id, extMap.get(fileType, 'script')))

def removePhonologyDirectory(phonology):
    """Remove the directory of the phonology model and everything in it.
    
    :param phonology: a phonology model object.
    :returns: an absolute path to the directory for the phonology.

    """
    try:
        phonologyDirPath = getPhonologyDirPath(phonology)
        rmtree(phonologyDirPath)
        return phonologyDirPath
    except Exception:
        return None
