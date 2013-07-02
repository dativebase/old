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

"""Contains the :class:`MorphologicalparsersController` and its auxiliary functions.

.. module:: morphologicalparsers
   :synopsis: Contains the morphological parsers controller and its auxiliary functions.

"""

import logging
import cPickle
import simplejson as json
import os
from uuid import uuid4
import codecs
from subprocess import Popen
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from shutil import rmtree
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import MorphologicalParserSchema, TranscriptionsSchema, MorphemeSequencesSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
import onlinelinguisticdatabase.lib.simplelm as simplelm
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import MorphologicalParser, MorphologicalParserBackup
from onlinelinguisticdatabase.lib.foma_worker import foma_worker_q

log = logging.getLogger(__name__)

class MorphologicalparsersController(BaseController):
    """Generate responses to requests on morphological parser resources.

    A morphological parser, as here conceived, is a morphophonological FST that is both a recognizer
    and a transducer, plus a morpheme-based language model that ranks candidate parses according to
    their probabilities.  The morphophonological FST component maps surface strings to sequences of
    morphemes and delimiters -- it is the composition of a pre-existing morphology FST and a pre-existing
    phonology FST.  The language model component is generated from the corpus specified in the language_model
    attribute.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('MorphologicalParser', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all morphological parser resources.

        :URL: ``GET /morphologicalparsers`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all morphological parser resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_morphological_parser(Session.query(MorphologicalParser))
            query = h.add_order_by(query, dict(request.GET), self.query_builder)
            return h.add_pagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """Create a new morphological parser resource and return it.

        :URL: ``POST /morphologicalparsers``
        :request body: JSON object representing the morphological parser to create.
        :returns: the newly created morphological parser.

        """
        try:
            schema = MorphologicalParserSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            morphological_parser = create_new_morphological_parser(data)
            Session.add(morphological_parser)
            Session.commit()
            create_morphological_parser_dir(morphological_parser)
            return morphological_parser
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
        """Return the data necessary to create a new morphological parser.

        :URL: ``GET /morphologicalparsers/new``.
        :returns: a dictionary containing summarizing the corpora, phonologies and morphologies.

        """
        return get_data_for_new_edit(dict(request.GET))

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a morphological parser and return it.

        :URL: ``PUT /morphologicalparsers/id``
        :Request body: JSON object representing the morphological parser with updated attribute values.
        :param str id: the ``id`` value of the morphological parser to be updated.
        :returns: the updated morphological parser model.

        """
        morphological_parser = h.eagerload_morphological_parser(Session.query(MorphologicalParser)).get(int(id))
        if morphological_parser:
            try:
                schema = MorphologicalParserSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                morphological_parser_dict = morphological_parser.get_dict()
                morphological_parser = update_morphological_parser(morphological_parser, data)
                # morphological_parser will be False if there are no changes (cf. update_morphological_parser).
                if morphological_parser:
                    backup_morphological_parser(morphological_parser_dict)
                    Session.add(morphological_parser)
                    Session.commit()
                    return morphological_parser
                else:
                    response.status_int = 400
                    return {'error': u'The update request failed because the submitted data were not new.'}
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no morphological parser with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing morphological parser and return it.

        :URL: ``DELETE /morphologicalparsers/id``
        :param str id: the ``id`` value of the morphological parser to be deleted.
        :returns: the deleted morphological parser model.

        """
        morphological_parser = h.eagerload_morphological_parser(Session.query(MorphologicalParser)).get(id)
        if morphological_parser:
            morphological_parser_dict = morphological_parser.get_dict()
            backup_morphological_parser(morphological_parser_dict)
            Session.delete(morphological_parser)
            Session.commit()
            remove_morphological_parser_directory(morphological_parser)
            return morphological_parser
        else:
            response.status_int = 404
            return {'error': 'There is no morphological parser with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a morphological parser.

        :URL: ``GET /morphologicalparsers/id``
        :param str id: the ``id`` value of the morphological parser to be returned.
        :GET param str script: if set to '1', the script will be returned with the morphological parser
        :returns: a morphological parser model object.

        """
        morphological_parser = h.eagerload_morphological_parser(Session.query(MorphologicalParser)).get(id)
        if morphological_parser:
            morphological_parser_dict = morphological_parser.get_dict()
            if request.GET.get('script') == u'1':
                morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
                morphological_parser_script_path = h.get_model_file_path(morphological_parser, morphological_parser_dir_path, file_type='script')
                if os.path.isfile(morphological_parser_script_path):
                    morphological_parser_dict['script'] = codecs.open(morphological_parser_script_path, mode='r', encoding='utf8').read()
                else:
                    morphological_parser_dict['script'] = u''
            return morphological_parser_dict
        else:
            response.status_int = 404
            return {'error': 'There is no morphological parser with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a morphological parser and the data needed to update it.

        :URL: ``GET /morphologicalparsers/id/edit``
        :param str id: the ``id`` value of the morphological parser that will be updated.
        :returns: a dictionary of the form::

                {"morphological_parser": {...}, "data": {...}}

            where the value of the ``morphological_parser`` key is a dictionary
            representation of the morphological_parser and the value of the ``data`` key
            is the data structure returned by the ``new`` action, i.e., a representation of
            the corpora, phonologies and morphologies in the system.

        """
        morphological_parser = h.eagerload_morphological_parser(Session.query(MorphologicalParser)).get(id)
        if morphological_parser:
            return {'data': get_data_for_new_edit(dict(request.GET)), 'morphological_parser': morphological_parser}
        else:
            response.status_int = 404
            return {'error': 'There is no morphological parser with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the morphological parser with ``morphological_parser.id==id`` and its previous versions.

        :URL: ``GET /morphologicalparsers/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            morphological parser whose history is requested.
        :returns: A dictionary of the form::

                {"morphological_parser": { ... }, "previous_versions": [ ... ]}

            where the value of the ``morphological_parser`` key is the morphological parser whose
            history is requested and the value of the ``previous_versions`` key
            is a list of dictionaries representing previous versions of the
            morphological parser.

        """
        morphological_parser, previous_versions = h.get_model_and_previous_versions('MorphologicalParser', id)
        if morphological_parser or previous_versions:
            return {'morphological_parser': morphological_parser,
                    'previous_versions': previous_versions}
        else:
            response.status_int = 404
            return {'error': 'No morphological parsers or morphological parser backups match %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def generate_and_compile(self, id):
        """Generate the morphological parser's morphophonology script and compile it as a foma FST.

        :URL: ``PUT /morphologicalparsers/generate_and_compile/id``
        :param str id: the ``id`` value of the morphologicalparser whose script will be compiled.
        :returns: if the morphological parser exists and foma is installed, the morphological parser
            model is returned;  ``GET /morphologicalparsers/id`` must be polled to
            determine when and how the compilation task has terminated.

        .. note::

            The script is compiled asynchronously in a worker thread.  See
            :mod:`onlinelinguisticdatabase.lib.foma_worker`.

        """
        return generate_and_compile_morphological_parser(id)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def generate(self, id):
        """Generate the morphological parser's morphophonology script but do not compile it.

        :URL: ``PUT /morphologicalparsers/generate/id``
        :param str id: the ``id`` value of the morphological parser whose script will be compiled.
        :returns: if the morphological parser exists and foma is installed, the morphological parser
            model is returned;  ``GET /morphologicalparsers/id`` must be polled to
            determine when the generation task has terminated.

        """
        return generate_and_compile_morphological_parser(id, compile_=False)

    @h.restrict('GET')
    @h.authenticate_with_JSON
    def servecompiled(self, id):
        """Serve the compiled foma script of the morphological parser.

        :URL: ``PUT /morphologicalparsers/servecompiled/id``
        :param str id: the ``id`` value of a morphological parser.
        :returns: a stream of bytes -- the compiled morphological parser script.  

        """
        morphological_parser = Session.query(MorphologicalParser).get(id)
        if morphological_parser:
            if h.foma_installed():
                morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
                foma_file_path  = h.get_model_file_path(morphological_parser, morphological_parser_dir_path, file_type='binary')
                if os.path.isfile(foma_file_path):
                    return forward(FileApp(foma_file_path))
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'The morphophonology foma script of '
                        'MorphologicalParser %d has not been compiled yet.' % morphological_parser.id})
            else:
                response.status_int = 400
                return json.dumps({'error': 'Foma and flookup are not installed.'})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no morphological parser with id %s' % id})

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def applydown(self, id):
        """Call foma apply down on the input in the request body using a morphological parser.

        :URL: ``PUT /morphologicalparsers/applydown/id``
        :param str id: the ``id`` value of the morphological parser that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphological parser exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply down.

        """
        return self.apply(id, 'down')

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def applyup(self, id):
        """Call foma apply up on the input in the request body using a morphological parser.

        :URL: ``PUT /morphologicalparsers/applyup/id``
        :param str id: the ``id`` value of the morphological parser that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphological parser exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply up.

        """
        return self.apply(id, 'up')

    def apply(self, id, direction):
        """Call foma apply in the direction of ``direction`` on the input in the request body using a morphological parser.

        :param str id: the ``id`` value of the morphological parser that will be used.
        :param str direction: the direction of foma application.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphological parser exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply up/down.

        """
        morphological_parser = Session.query(MorphologicalParser).get(id)
        if morphological_parser:
            if h.foma_installed():
                morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
                morphological_parser_binary_path = h.get_model_file_path(morphological_parser, morphological_parser_dir_path, file_type='binary')
                if os.path.isfile(morphological_parser_binary_path):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        schema, key = {'up': (TranscriptionsSchema, 'transcriptions'),
                                       'down': (MorphemeSequencesSchema, 'morpheme_sequences')}.\
                                        get(direction, (MorphemeSequencesSchema, 'morpheme_sequences'))
                        inputs = schema.to_python(inputs)
                        return foma_apply(direction, inputs[key], morphological_parser,
                                                 morphological_parser_binary_path, session['user'])
                    except h.JSONDecodeError:
                        response.status_int = 400
                        return h.JSONDecodeErrorResponse
                    except Invalid, e:
                        response.status_int = 400
                        return {'errors': e.unpack_errors()}
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'The morphophonology foma script of '
                        'MorphologicalParser %d has not been compiled yet.' % morphological_parser.id})
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no morphological parser with id %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def parse(self, id):
        """Parse the input word transcriptions using the morphological parser with id=``id``.

        :param str id: the ``id`` value of the morphological parser that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphological parser exists and foma is installed, a JSON object
            of the form ``{t1: p1, t2: p2, ...}`` where ``t1`` and ``t2`` are transcriptions
            of words from the request body and ``p1`` and ``p2`` are the most probable morphological
            parsers of t1 and t2.

        """
        morphological_parser = Session.query(MorphologicalParser).get(id)
        if not morphological_parser:
            response.status_int = 404
            return {'error': 'There is no morphological parser with id %s' % id}
        if not h.foma_installed():
            response.status_int = 400
            return {'error': 'Foma and flookup are not installed.'}
        morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
        morphological_parser_binary_path = h.get_model_file_path(morphological_parser, morphological_parser_dir_path, file_type='binary')
        if not os.path.isfile(morphological_parser_binary_path):
            response.status_int = 400
            return json.dumps({'error': 'The morphophonology foma script of '
                'MorphologicalParser %d has not been compiled yet.' % morphological_parser.id})
        morpheme_language_model_dir_path = h.get_model_directory_path(morphological_parser.language_model, config)
        lm_pickle_path = h.get_model_file_path(morphological_parser.language_model, morpheme_language_model_dir_path,
                file_type='lm_trie')
        if not os.path.isfile(lm_pickle_path):
            response.status_int = 404
            return {'error': 'The morpheme language model was not written to disk.'}
        try:
            lm_trie = cPickle.load(open(lm_pickle_path, 'rb'))
        except Exception:
            response.status_int = 400
            return {'error': 'An error occurred while trying to retrieve the language model.'}
        try:
            morpheme_splitter = h.get_morpheme_splitter()
            inputs = json.loads(unicode(request.body, request.charset))
            schema = TranscriptionsSchema
            inputs = schema.to_python(inputs)
            candidates = foma_apply('up', inputs['transcriptions'], morphological_parser,
                                        morphological_parser_binary_path, session['user'])
            return dict((transcription, get_most_probable_parse(lm_trie, candidate_parses, morpheme_splitter))
                          for transcription, candidate_parses in candidates.iteritems())
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

def get_most_probable_parse(language_model_trie, candidates, morpheme_splitter):
    """Return the most probable parse from within the list of parses in candidates.

    :param instance language_model_trie: a simplm.LMTrie instance encoding a morpheme LM.
    :param list candidates: candidate parses as strings of morphemes and delimiters.
    :param func morpheme_splitter: function that splits a string into morphemes and delimiters.
    :returns: the candidate parse (as a string) with the greatest probability.

    """
    candidates_probs = []
    for candidate in candidates:
        morpheme_sequence = [h.lm_start] + morpheme_splitter(candidate)[::2] + [h.lm_end]
        candidates_probs.append((candidate, simplelm.compute_sentence_prob(language_model_trie, morpheme_sequence)))
    candidates_probs.sort(key=lambda x: x[1])
    return candidates_probs[-1][0]

def get_data_for_new_edit(GET_params):
    """Return the data needed to create a new morphological parser or edit one."""
    model_name_map = {
        'morpheme_language_models': 'MorphemeLanguageModel',
        'phonologies': 'Phonology',
        'morphologies': 'Morphology'
    }
    getter_map = {
        'morpheme_language_models': h.get_mini_dicts_getter('MorphemeLanguageModel'),
        'phonologies': h.get_mini_dicts_getter('Phonology'),
        'morphologies': h.get_mini_dicts_getter('Morphology')
    }
    return h.get_data_for_new_action(GET_params, getter_map, model_name_map)

################################################################################
# Backup morphological_parser
################################################################################

def backup_morphological_parser(morphological_parser_dict):
    """Backup a morphological parser.

    :param dict morphological_parser_dict: a representation of a morphological parser model.
    :returns: ``None``

    """
    morphological_parser_backup = MorphologicalParserBackup()
    morphological_parser_backup.vivify(morphological_parser_dict)
    Session.add(morphological_parser_backup)


################################################################################
# MorphologicalParser Create & Update Functions
################################################################################

def create_new_morphological_parser(data):
    """Create a new morphological parser.

    :param dict data: the data for the morphological parser to be created.
    :returns: an SQLAlchemy model object representing the morphological parser.

    """
    morphological_parser = MorphologicalParser()
    morphological_parser.UUID = unicode(uuid4())
    morphological_parser.name = h.normalize(data['name'])
    morphological_parser.description = h.normalize(data['description'])
    morphological_parser.enterer = morphological_parser.modifier = session['user']
    morphological_parser.datetime_modified = morphological_parser.datetime_entered = h.now()
    morphological_parser.phonology = data['phonology']
    morphological_parser.morphology = data['morphology']
    morphological_parser.language_model = data['language_model']
    return morphological_parser

def update_morphological_parser(morphological_parser, data):
    """Update a morphological parser.

    :param morphological_parser: the morphological parser model to be updated.
    :param dict data: representation of the updated morphological parser.
    :returns: the updated morphological parser model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = h.set_attr(morphological_parser, 'name', h.normalize(data['name']), changed)
    changed = h.set_attr(morphological_parser, 'description', h.normalize(data['description']), changed)
    changed = h.set_attr(morphological_parser, 'phonology', data['phonology'], changed)
    changed = h.set_attr(morphological_parser, 'morphology', data['morphology'], changed)
    changed = h.set_attr(morphological_parser, 'language_model', data['language_model'], changed)
    if changed:
        session['user'] = Session.merge(session['user'])
        morphological_parser.modifier = session['user']
        morphological_parser.datetime_modified = h.now()
        return morphological_parser
    return changed

def create_morphological_parser_dir(morphological_parser):
    """Create the directory to hold the morphological parser script and auxiliary files.

    :param morphological_parser: a morphological parser model object.
    :returns: an absolute path to the directory for the morphological parser.

    """
    morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
    h.make_directory_safely(morphological_parser_dir_path)
    return morphological_parser_dir_path

def generate_and_compile_morphological_parser(morphological_parser_id, compile_=True):
    morphological_parser = Session.query(MorphologicalParser).get(morphological_parser_id)
    if not morphological_parser:
        response.status_int = 404
        return {'error': 'There is no morphological parser with id %s' % id}
    if compile_ and not h.foma_installed():
        response.status_int = 400
        return {'error': 'Foma and flookup are not installed.'}
    morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
    morphology_dir_path = h.get_model_directory_path(morphological_parser.morphology, config)
    phonology_dir_path = h.get_model_directory_path(morphological_parser.phonology, config)
    verification_string = u'defined morphophonology: '
    foma_worker_q.put({
        'id': h.generate_salt(),
        'func': 'create_morphological_parser_components',
        'args': {
            'morphological_parser_id': morphological_parser.id,
            'compile': compile_,
            'script_dir_path': morphological_parser_dir_path,
            'morphology_dir_path': morphology_dir_path,
            'phonology_dir_path': phonology_dir_path,
            'user_id': session['user'].id,
            'verification_string': verification_string,
            'timeout': h.morphological_parser_compile_timeout
        }
    })
    return morphological_parser

def remove_morphological_parser_directory(morphological_parser):
    """Remove the directory of the morphological parser model and everything in it.

    :param morphological_parser: a morphological parser model object.
    :returns: an absolute path to the directory for the morphological parser.

    """
    try:
        morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
        rmtree(morphological_parser_dir_path)
        return morphological_parser_dir_path
    except Exception:
        return None

def foma_apply(direction, inputs, morphological_parser, morphological_parser_binary_path, user):
    """Foma-apply the inputs in the direction of ``direction`` using the morphological parser's compiled foma script.

    :param str direction: the direction in which to use the transducer
    :param list inputs: a list of surface transcriptions or morpheme sequences.
    :param morphological_parser: a morphological parser model.
    :param str morphological_parser_binary_path: an absolute path to a compiled morphological parser script.
    :param user: a user model.
    :returns: a dictionary: ``{input1: [o1, o2, ...], input2: [...], ...}``

    """
    random_string = h.generate_salt()
    morphological_parser_dir_path = h.get_model_directory_path(morphological_parser, config)
    inputs_file_path = os.path.join(morphological_parser_dir_path,
            'inputs_%s_%s.txt' % (user.username, random_string))
    outputs_file_path = os.path.join(morphological_parser_dir_path,
            'outputs_%s_%s.txt' % (user.username, random_string))
    apply_file_path = os.path.join(morphological_parser_dir_path,
            'apply_%s_%s.sh' % (user.username, random_string))
    with codecs.open(inputs_file_path, 'w', 'utf8') as f:
        inputs = [u'%s%s%s' % (h.word_boundary_symbol, input_, h.word_boundary_symbol)
                  for input_ in inputs]
        f.write(u'\n'.join(inputs))
    with codecs.open(apply_file_path, 'w', 'utf8') as f:
        f.write('#!/bin/sh\ncat %s | flookup %s%s' % (
            inputs_file_path, {'up': '', 'down': '-i '}.get(direction, '-i '), morphological_parser_binary_path))
    os.chmod(apply_file_path, 0744)
    with open(os.devnull, 'w') as devnull:
        with codecs.open(outputs_file_path, 'w', 'utf8') as outfile:
            p = Popen(apply_file_path, shell=False, stdout=outfile, stderr=devnull)
    p.communicate()
    with codecs.open(outputs_file_path, 'r', 'utf8') as f:
        result = h.foma_output_file2dict(f)
    os.remove(inputs_file_path)
    os.remove(outputs_file_path)
    os.remove(apply_file_path)
    return result

