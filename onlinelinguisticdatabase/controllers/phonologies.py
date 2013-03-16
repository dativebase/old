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
from uuid import uuid4
import codecs
from subprocess import call, PIPE, Popen
from shutil import rmtree
from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import PhonologySchema, MorphophonemicTranscriptionsSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Phonology, PhonologyBackup
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
                phonologyDict = phonology.getDict()
                phonology = updatePhonology(phonology, data)
                # phonology will be False if there are no changes (cf. updatePhonology).
                if phonology:
                    backupPhonology(phonologyDict)
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
            phonologyDict = phonology.getDict()
            backupPhonology(phonologyDict)
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
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the phonology with ``phonology.id==id`` and its previous versions.

        :URL: ``GET /phonologies/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            phonology whose history is requested.
        :returns: A dictionary of the form::

                {"phonology": { ... }, "previousVersions": [ ... ]}

            where the value of the ``phonology`` key is the phonology whose
            history is requested and the value of the ``previousVersions`` key
            is a list of dictionaries representing previous versions of the
            phonology.

        """
        phonology, previousVersions = h.getModelAndPreviousVersions('Phonology', id)
        if phonology or previousVersions:
            return {'phonology': phonology,
                    'previousVersions': previousVersions}
        else:
            response.status_int = 404
            return {'error': 'No phonologies or phonology backups match %s' % id}

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
                return {'error': 'Foma and flookup are not installed.'}
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
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the phonology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            phonologized outputs of ``t1``.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.fomaInstalled():
                phonologyBinaryPath = getPhonologyFilePath(phonology, 'binary')
                if os.path.isfile(phonologyBinaryPath):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        inputs = MorphophonemicTranscriptionsSchema.to_python(inputs)
                        return phonologize(inputs['transcriptions'], phonology,
                                                 phonologyBinaryPath, session['user'])
                    except h.JSONDecodeError:
                        response.status_int = 400
                        return h.JSONDecodeErrorResponse
                    except Invalid, e:
                        response.status_int = 400
                        return {'errors': e.unpack_errors()}
                else:
                    response.status_int = 400
                    return {'error': 'Phonology %d has not been compiled yet.' % phonology.id}
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def runtests(self, id):
        """Run the tests defined in the phonology's script against the phonology.

        A line in a phonology's script that begins with "#test" signifies a
        test.  After "#test" there should be a string of characters followed by
        "->" followed by another string of characters.  The first string is the
        underlying representation and the second is the anticipated surface
        representation.  Requests to ``GET /phonologies/runtests/id`` will cause
        the OLD to run a phonology script against its tests and return a
        dictionary detailing the expected and actual outputs of each input in
        the transcription.

        :URL: ``GET /phonologies/runtests/id``
        :param str id: the ``id`` value of the phonology that will be tested.
        :returns: if the phonology exists and foma is installed, a JSON object
            representing the results of the test.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.fomaInstalled():
                phonologyBinaryPath = getPhonologyFilePath(phonology, 'binary')
                if os.path.isfile(phonologyBinaryPath):
                    return runTests(phonology, phonologyBinaryPath, session['user'])
                else:
                    response.status_int = 400
                    return {'error': 'Phonology %d has not been compiled yet.' % phonology.id}
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}


################################################################################
# Backup phonology
################################################################################

def backupPhonology(phonologyDict):
    """Backup a phonology.

    :param dict phonologyDict: a representation of a phonology model.
    :returns: ``None``

    """
    phonologyBackup = PhonologyBackup()
    phonologyBackup.vivify(phonologyDict)
    Session.add(phonologyBackup)


################################################################################
# Phonology Create & Update Functions
################################################################################

def createNewPhonology(data):
    """Create a new phonology.

    :param dict data: the data for the phonology to be created.
    :returns: an SQLAlchemy model object representing the phonology.

    """
    phonology = Phonology()
    phonology.UUID = unicode(uuid4())

    phonology.name = h.normalize(data['name'])
    phonology.description = h.normalize(data['description'])
    phonology.script = h.normalize(data['script'])  # normalize or not?

    phonology.enterer = phonology.modifier = session['user']
    phonology.datetimeModified = phonology.datetimeEntered = h.now()
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
        phonology.datetimeModified = h.now()
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


def fomaOutputFile2Dict(file_):
    """Return the content of the foma output file ``file_`` as a dict.

    :param file file_: utf8-encoded file object with tab-delimited i/o pairs.
    :returns: dictionary of the form ``{i1: [01, 02, ...], i2: [...], ...}``.

    """
    result = {}
    for line in file_:
        line = line.strip()
        if line:
            i, o = line.split('\t')[:2]
            try:
                result[i].append(o)
            except (KeyError, ValueError):
                result[i] = [o]
    return result

def phonologize(inputs, phonology, phonologyBinaryPath, user):
    """Phonologize the inputs using the phonology's compiled script.
    
    :param list inputs: a list of morpho-phonemic transcriptions.
    :param phonology: a phonology model.
    :param str phonologyBinaryPath: an absolute path to a compiled phonology script.
    :param user: a user model.
    :returns: a dictionary: ``{input1: [o1, o2, ...], input2: [...], ...}``

    """
    randomString = h.generateSalt()
    phonologyDirPath = getPhonologyDirPath(phonology)
    inputsFilePath = os.path.join(phonologyDirPath,
            'inputs_%s_%s.txt' % (user.username, randomString))
    outputsFilePath = os.path.join(phonologyDirPath,
            'outputs_%s_%s.txt' % (user.username, randomString))
    applydownFilePath = os.path.join(phonologyDirPath,
            'applydown_%s_%s.sh' % (user.username, randomString))
    with codecs.open(inputsFilePath, 'w', 'utf8') as f:
        f.write(u'\n'.join(inputs))
    with codecs.open(applydownFilePath, 'w', 'utf8') as f:
        f.write('#!/bin/sh\ncat %s | flookup -i %s' % (
                inputsFilePath, phonologyBinaryPath))
    os.chmod(applydownFilePath, 0744)
    with open(os.devnull, 'w') as devnull:
        with codecs.open(outputsFilePath, 'w', 'utf8') as outfile:
            p = Popen(applydownFilePath, shell=False, stdout=outfile, stderr=devnull)
    p.communicate()
    with codecs.open(outputsFilePath, 'r', 'utf8') as f:
        result = fomaOutputFile2Dict(f)
    os.remove(inputsFilePath)
    os.remove(outputsFilePath)
    os.remove(applydownFilePath)
    return result


def getTests(phonology):
    """Return any tests defined in a phonology's script as a dictionary."""
    result = {}
    testLines = [l[6:] for l in phonology.script.splitlines() if l[:6] == u'#test ']
    for l in testLines:
        try:
            i, o = map(unicode.strip, l.split(u'->'))
            try:
                result[i].append(o)
            except KeyError:
                result[i] = [o]
        except ValueError:
            pass
    return result


def runTests(phonology, phonologyBinaryPath, user):
    """Run the test defined in the phonology's script and return a report.
    
    :param phonology: a phonology model.
    :param str phonologyBinaryPath: an absolute path to the phonology's compiled foma script.
    :param user: a user model.
    :returns: a dictionary representing the report on the tests.

    A line in a phonology's script that begins with "#test " signifies a
    test.  After "#test " there should be a string of characters followed by
    "->" followed by another string of characters.  The first string is the
    underlying representation and the second is the anticipated surface
    representation.  Requests to ``GET /phonologies/runtests/id`` will cause
    the OLD to run a phonology script against its tests and return a
    dictionary detailing the expected and actual outputs of each input in the
    transcription.  :func:`runTests` generates that dictionary.

    """

    tests = getTests(phonology)
    if not tests:
        response.status_int = 400
        return {'error': 'The script of phonology %d contains no tests.' % phonology.id}
    results = phonologize(tests.keys(), phonology, phonologyBinaryPath, user)
    return dict([(t, {'expected': tests[t], 'actual': results[t]}) for t in tests])
