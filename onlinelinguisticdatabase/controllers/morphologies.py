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

"""Contains the :class:`MorphologiesController` and its auxiliary functions.

.. module:: morphologies
   :synopsis: Contains the morphologies controller and its auxiliary functions.

"""

import logging
import simplejson as json
import os
import cPickle
from uuid import uuid4
import codecs
from subprocess import Popen
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from shutil import rmtree
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import MorphologySchema, MorphemeSequencesSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Morphology, MorphologyBackup
from onlinelinguisticdatabase.lib.foma_worker import foma_worker_q

log = logging.getLogger(__name__)

class MorphologiesController(BaseController):
    """Generate responses to requests on morphology resources.

    A morphology, as here conceived, is an FST that is both a recognizer and a transducer, i.e.,
    it recognizes only those sequences of morphemes that are form valid words and it maps sequences
    of morphemes (in the general sense) to sequences of morpheme *forms*.  By a morpheme in the general
    sense, I mean to refer to ordered pairs of morpheme form and morpheme gloss.  That is, an OLD 
    morphology is an FST that maps something like 'chien|dog-s|PL' to 'chien-s' (and vice versa) and 
    which does not recognize 's|PL-chien|dog'.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    TODO: consider generating values for ``lexiconScript`` and ``rulesScript`` attributes
    which, by default, are concatenated to produce a value for the ``script`` attribute but 
    where such default auto-generation can be overridden by the user so that, for example, the
    auto-generated subscripts could be used to hand-write a more intelligent morphology FST script.

    """

    queryBuilder = SQLAQueryBuilder('Morphology', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all morphology resources.

        :URL: ``GET /morphologies`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all morphology resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerloadMorphology(Session.query(Morphology))
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
        """Create a new morphology resource and return it.

        :URL: ``POST /morphologies``
        :request body: JSON object representing the morphology to create.
        :returns: the newly created morphology.

        """
        try:
            schema = MorphologySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            morphology = create_new_morphology(data)
            Session.add(morphology)
            Session.commit()
            create_morphology_dir(morphology)
            return morphology
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
        """Return the data necessary to create a new morphology.

        :URL: ``GET /morphologies/new``.
        :returns: a dictionary containing summarizing the corpora.

        """
        return getDataForNewEdit(dict(request.GET))

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a morphology and return it.

        :URL: ``PUT /morphologies/id``
        :Request body: JSON object representing the morphology with updated attribute values.
        :param str id: the ``id`` value of the morphology to be updated.
        :returns: the updated morphology model.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(int(id))
        if morphology:
            try:
                schema = MorphologySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                morphologyDict = morphology.getDict()
                morphology = update_morphology(morphology, data)
                # morphology will be False if there are no changes (cf. update_morphology).
                if morphology:
                    backupMorphology(morphologyDict)
                    Session.add(morphology)
                    Session.commit()
                    return morphology
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
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing morphology and return it.

        :URL: ``DELETE /morphologies/id``
        :param str id: the ``id`` value of the morphology to be deleted.
        :returns: the deleted morphology model.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(id)
        if morphology:
            morphologyDict = morphology.getDict()
            backupMorphology(morphologyDict)
            Session.delete(morphology)
            Session.commit()
            remove_morphology_directory(morphology)
            return morphology
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a morphology.

        :URL: ``GET /morphologies/id``
        :param str id: the ``id`` value of the morphology to be returned.
        :GET param str script: if set to '1', the script will be returned with the morphology
        :returns: a morphology model object.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(id)
        if morphology:
            morphology_dict = morphology.getDict()
            if request.GET.get('script') == u'1':
                morphology_script_path = get_morphology_file_path(morphology, fileType='script')
                if os.path.isfile(morphology_script_path):
                    morphology_dict['script'] = codecs.open(morphology_script_path, mode='r', encoding='utf8').read()
                else:
                    morphology_dict['script'] = u''
            if request.GET.get('lexicon') == u'1':
                morphology_lexicon_path = get_morphology_file_path(morphology, fileType='lexicon')
                if os.path.isfile(morphology_lexicon_path):
                    morphology_dict['lexicon'] = cPickle.load(open(morphology_lexicon_path, 'rb'))
                else:
                    morphology_dict['lexicon'] = {}
            return morphology_dict
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a morphology and the data needed to update it.

        :URL: ``GET /morphologies/id/edit``
        :param str id: the ``id`` value of the morphology that will be updated.
        :returns: a dictionary of the form::

                {"morphology": {...}, "data": {...}}

            where the value of the ``morphology`` key is a dictionary
            representation of the morphology and the value of the ``data`` key
            is an empty dictionary.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(id)
        if morphology:
            return {'data': getDataForNewEdit(dict(request.GET)), 'morphology': morphology}
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the morphology with ``morphology.id==id`` and its previous versions.

        :URL: ``GET /morphologies/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            morphology whose history is requested.
        :returns: A dictionary of the form::

                {"morphology": { ... }, "previousVersions": [ ... ]}

            where the value of the ``morphology`` key is the morphology whose
            history is requested and the value of the ``previousVersions`` key
            is a list of dictionaries representing previous versions of the
            morphology.

        """
        morphology, previousVersions = h.getModelAndPreviousVersions('Morphology', id)
        if morphology or previousVersions:
            return {'morphology': morphology,
                    'previousVersions': previousVersions}
        else:
            response.status_int = 404
            return {'error': 'No morphologies or morphology backups match %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def generate_and_compile(self, id):
        """Generate the morphology's script and compile it as a foma FST.

        :URL: ``PUT /morphologies/compile/id``
        :param str id: the ``id`` value of the morphology whose script will be compiled.
        :returns: if the morphology exists and foma is installed, the morphology
            model is returned;  ``GET /morphologies/id`` must be polled to
            determine when and how the compilation task has terminated.

        .. note::

            The script is compiled asynchronously in a worker thread.  See
            :mod:`onlinelinguisticdatabase.lib.foma_worker`.

        """
        return generate_and_compile_morphology(id)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def generate(self, id):
        """Generate the morphology's script -- do not compile it.

        :URL: ``PUT /morphologies/compile/id``
        :param str id: the ``id`` value of the morphology whose script will be compiled.
        :returns: if the morphology exists and foma is installed, the morphology
            model is returned;  ``GET /morphologies/id`` must be polled to
            determine when the generation task has terminated.

        """
        return generate_and_compile_morphology(id, compile_=False)

    @h.restrict('GET')
    @h.authenticateWithJSON
    def servecompiled(self, id):
        """Serve the compiled foma script of the morphology.

        :URL: ``PUT /morphologies/servecompiled/id``
        :param str id: the ``id`` value of a morphology.
        :returns: a stream of bytes -- the compiled morphology script.  

        """
        morphology = Session.query(Morphology).get(id)
        if morphology:
            if h.fomaInstalled():
                fomaFilePath = get_morphology_file_path(morphology, 'binary')
                if os.path.isfile(fomaFilePath):
                    return forward(FileApp(fomaFilePath))
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'Morphology %d has not been compiled yet.' % morphology.id})
            else:
                response.status_int = 400
                return json.dumps({'error': 'Foma and flookup are not installed.'})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no morphology with id %s' % id})

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def applydown(self, id):
        """Call foma apply down on the input in the request body using a morphology.

        :URL: ``PUT /morphologies/applydown/id``
        :param str id: the ``id`` value of the morphology that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply down.

        """
        return self.apply(id, 'down')

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def applyup(self, id):
        """Call foma apply up on the input in the request body using a morphology.

        :URL: ``PUT /morphologies/applyup/id``
        :param str id: the ``id`` value of the morphology that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply up.

        """
        return self.apply(id, 'up')

    def apply(self, id, direction):
        """Call foma apply in the direction of ``direction`` on the input in the request body using a morphology.

        :param str id: the ``id`` value of the morphology that will be used.
        :param str direction: the direction of foma application.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply up/down.

        """
        morphology = Session.query(Morphology).get(id)
        if morphology:
            if h.fomaInstalled():
                morphology_binary_path = get_morphology_file_path(morphology, 'binary')
                if os.path.isfile(morphology_binary_path):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        inputs = MorphemeSequencesSchema.to_python(inputs)
                        return foma_apply(direction, inputs['morphemeSequences'], morphology,
                                                 morphology_binary_path, session['user'])
                    except h.JSONDecodeError:
                        response.status_int = 400
                        return h.JSONDecodeErrorResponse
                    except Invalid, e:
                        response.status_int = 400
                        return {'errors': e.unpack_errors()}
                else:
                    response.status_int = 400
                    return {'error': 'Morphology %d has not been compiled yet.' % morphology.id}
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

def getDataForNewEdit(GET_params):
    """Return the data needed to create a new morphology or edit one."""
    modelNameMap = {'corpora': 'Corpus'}
    getterMap = {'corpora': h.getMiniDictsGetter('Corpus')}
    return h.getDataForNewAction(GET_params, getterMap, modelNameMap)

################################################################################
# Backup morphology
################################################################################

def backupMorphology(morphologyDict):
    """Backup a morphology.

    :param dict morphologyDict: a representation of a morphology model.
    :returns: ``None``

    """
    morphologyBackup = MorphologyBackup()
    morphologyBackup.vivify(morphologyDict)
    Session.add(morphologyBackup)


################################################################################
# Morphology Create & Update Functions
################################################################################

def create_new_morphology(data):
    """Create a new morphology.

    :param dict data: the data for the morphology to be created.
    :returns: an SQLAlchemy model object representing the morphology.

    """
    morphology = Morphology()
    morphology.UUID = unicode(uuid4())
    morphology.name = h.normalize(data['name'])
    morphology.description = h.normalize(data['description'])
    morphology.enterer = morphology.modifier = session['user']
    morphology.datetimeModified = morphology.datetimeEntered = h.now()
    morphology.lexiconCorpus = data['lexiconCorpus']
    morphology.rulesCorpus = data['rulesCorpus']
    morphology.script_type = data['script_type']
    morphology.extract_morphemes_from_rules_corpus = data['extract_morphemes_from_rules_corpus']
    return morphology

def update_morphology(morphology, data):
    """Update a morphology.

    :param morphology: the morphology model to be updated.
    :param dict data: representation of the updated morphology.
    :returns: the updated morphology model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = h.setAttr(morphology, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(morphology, 'description', h.normalize(data['description']), changed)
    changed = h.setAttr(morphology, 'lexiconCorpus', data['lexiconCorpus'], changed)
    changed = h.setAttr(morphology, 'rulesCorpus', data['rulesCorpus'], changed)
    changed = h.setAttr(morphology, 'script_type', data['script_type'], changed)
    changed = h.setAttr(morphology, 'extract_morphemes_from_rules_corpus', data['extract_morphemes_from_rules_corpus'], changed)
    if changed:
        session['user'] = Session.merge(session['user'])
        morphology.modifier = session['user']
        morphology.datetimeModified = h.now()
        return morphology
    return changed

def get_morphology_dir_path(morphology):
    """Return the path to a morphology's directory.

    :param morphology: a morphology model object.
    :returns: an absolute path to the directory for the morphology.

    """
    return os.path.join(h.getOLDDirectoryPath('morphologies', config=config),
                        'morphology_%d' % morphology.id)

def create_morphology_dir(morphology):
    """Create the directory to hold the morphology script and auxiliary files.

    :param morphology: a morphology model object.
    :returns: an absolute path to the directory for the morphology.

    """
    morphology_dir_path = get_morphology_dir_path(morphology)
    h.makeDirectorySafely(morphology_dir_path)
    return morphology_dir_path

def get_morphology_file_path(morphology, fileType='script'):
    """Return the path to a morphology's file of the given type.

    :param morphology: a morphology model object.
    :param str fileType: one of 'script', 'binary', 'compiler', or 'tester'.
    :returns: an absolute path to the morphology's script file.

    """
    ext_map = {
        'script': 'script',
        'binary': 'foma',
        'compiler': 'sh',
        'log': 'log',
        'lexicon': 'pickle'
    }
    return os.path.join(get_morphology_dir_path(morphology),
            'morphology_%d.%s' % (morphology.id, ext_map.get(fileType, 'script')))

def generate_and_compile_morphology(morphology_id, compile_=True):
    morphology = Session.query(Morphology).get(morphology_id)
    if not morphology:
        response.status_int = 404
        return {'error': 'There is no morphology with id %s' % id}
    if compile_ and not h.fomaInstalled():
        response.status_int = 400
        return {'error': 'Foma and flookup are not installed.'}
    morphology_dir_path = get_morphology_dir_path(morphology)
    verification_string = {'lexc': u'Done!', 'regex': u'defined morphology: '}.get(
        morphology.script_type, u'Done!')
    foma_worker_q.put({
        'id': h.generateSalt(),
        'func': 'generate_and_compile_morphology_script',
        'args': {'morphology_id': morphology.id, 'compile': compile_,
            'script_dir_path': morphology_dir_path, 'user_id': session['user'].id,
            'verification_string': verification_string, 'timeout': h.morphologyCompileTimeout}
    })
    return morphology

def remove_morphology_directory(morphology):
    """Remove the directory of the morphology model and everything in it.
    
    :param morphology: a morphology model object.
    :returns: an absolute path to the directory for the morphology.

    """
    try:
        morphology_dir_path = get_morphology_dir_path(morphology)
        rmtree(morphology_dir_path)
        return morphology_dir_path
    except Exception:
        return None

def foma_apply(direction, inputs, morphology, morphology_binary_path, user):
    """Foma-apply the inputs in the direction of ``direction`` using the morphology's compiled foma script.

    :param str direction: the direction in which to use the transducer
    :param list inputs: a list of morpho-phonemic transcriptions.
    :param morphology: a morphology model.
    :param str morphology_binary_path: an absolute path to a compiled morphology script.
    :param user: a user model.
    :returns: a dictionary: ``{input1: [o1, o2, ...], input2: [...], ...}``

    """
    random_string = h.generateSalt()
    morphology_dir_path = get_morphology_dir_path(morphology)
    inputs_file_path = os.path.join(morphology_dir_path,
            'inputs_%s_%s.txt' % (user.username, random_string))
    outputs_file_path = os.path.join(morphology_dir_path,
            'outputs_%s_%s.txt' % (user.username, random_string))
    apply_file_path = os.path.join(morphology_dir_path,
            'apply_%s_%s.sh' % (user.username, random_string))
    with codecs.open(inputs_file_path, 'w', 'utf8') as f:
        f.write(u'\n'.join(inputs))
    with codecs.open(apply_file_path, 'w', 'utf8') as f:
        f.write('#!/bin/sh\ncat %s | flookup %s%s' % (
            inputs_file_path, {'up': '', 'down': '-i '}.get(direction, '-i '), morphology_binary_path))
    os.chmod(apply_file_path, 0744)
    with open(os.devnull, 'w') as devnull:
        with codecs.open(outputs_file_path, 'w', 'utf8') as outfile:
            p = Popen(apply_file_path, shell=False, stdout=outfile, stderr=devnull)
    p.communicate()
    with codecs.open(outputs_file_path, 'r', 'utf8') as f:
        result = h.fomaOutputFile2Dict(f, remove_word_boundaries=False)
    os.remove(inputs_file_path)
    os.remove(outputs_file_path)
    os.remove(apply_file_path)
    return result
