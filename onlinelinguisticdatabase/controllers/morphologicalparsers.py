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
import simplejson as json
import os
from shutil import copytree, copyfile, rmtree
from uuid import uuid4
import codecs
import cPickle
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import MorphologicalParserSchema, TranscriptionsSchema, MorphemeSequencesSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
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
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of morphological parser resources matching the input
        JSON query.

        :URL: ``SEARCH /morphologicalparsers``
          (or ``POST /morphologicalparsers/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        """
        try:
            json_search_params = unicode(request.body, request.charset)
            python_search_params = json.loads(json_search_params)
            query = self.query_builder.get_SQLA_query(python_search_params.get('query'))
            return h.add_pagination(query, python_search_params.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except:
            response.status_int = 400
            return {'error': u'The specified search parameters generated an invalid database query'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """Return the data necessary to search the morphological parser resources.

        :URL: ``GET /morphologicalparsers/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}


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
            parser = create_new_morphological_parser(data)
            Session.add(parser)
            Session.commit()
            parser.make_directory_safely(parser.directory)
            return parser
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
        parser = h.eagerload_morphological_parser(Session.query(MorphologicalParser)).get(id)
        if parser:
            parser_dict = parser.get_dict()
            backup_morphological_parser(parser_dict)
            Session.delete(parser)
            Session.commit()
            parser.remove_directory()
            return parser
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
        parser = Session.query(MorphologicalParser).get(id)
        if parser:
            if h.foma_installed():
                binary_path = parser.get_file_path('binary')
                if os.path.isfile(binary_path):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        schema, key = {'up': (TranscriptionsSchema, 'transcriptions'),
                                       'down': (MorphemeSequencesSchema, 'morpheme_sequences')}.\
                                        get(direction, (MorphemeSequencesSchema, 'morpheme_sequences'))
                        inputs = schema.to_python(inputs)
                        return parser.apply(direction, inputs[key])
                    except h.JSONDecodeError:
                        response.status_int = 400
                        return h.JSONDecodeErrorResponse
                    except Invalid, e:
                        response.status_int = 400
                        return {'errors': e.unpack_errors()}
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'The morphophonology foma script of '
                        'MorphologicalParser %d has not been compiled yet.' % parser.id})
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
        parser = Session.query(MorphologicalParser).get(id)
        if not parser:
            response.status_int = 404
            return {'error': 'There is no morphological parser with id %s' % id}
        if not h.foma_installed():
            response.status_int = 400
            return {'error': 'Foma and flookup are not installed.'}
        try:
            inputs = json.loads(unicode(request.body, request.charset))
            schema = TranscriptionsSchema
            inputs = schema.to_python(inputs)
            inputs = [h.normalize(w) for w in inputs['transcriptions']]
            parses = parser.parse(inputs)
            # TODO: allow for a param which causes the candidates to be
            # returned as well as/instead of only the most probable parse
            # candidate.
            return dict((transcription, parse) for transcription, (parse, candidates) in
                        parses.iteritems())
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except Exception, e:
            log.warn(e)
            response.status_int = 400
            return {'error': u'Parse request raised an error.'}

    @h.restrict('GET')
    @h.authenticate_with_JSON
    @h.authorize(['administrator', 'contributor'])
    def servecompiled(self, id):
        """Serve the compiled foma script of the morphophonology FST of the morphological parser.

        :URL: ``PUT /morphologicalparsers/servecompiled/id``
        :param str id: the ``id`` value of a morphological parser.
        :returns: a stream of bytes -- the compiled morphological parser script.  

        """
        parser = Session.query(MorphologicalParser).get(id)
        if parser:
            if h.foma_installed():
                binary_path = parser.get_file_path('binary')
                if os.path.isfile(binary_path):
                    return forward(FileApp(binary_path))
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'The morphophonology foma script of '
                        'MorphologicalParser %d has not been compiled yet.' % parser.id})
            else:
                response.status_int = 400
                return json.dumps({'error': 'Foma and flookup are not installed.'})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no morphological parser with id %s' % id})

    @h.restrict('GET')
    @h.authenticate_with_JSON
    @h.authorize(['administrator', 'contributor'])
    def export_deprecated(self, id):
        """Export the parser as a self-contained archive including a Python interface and all required files.
        """
        try:
            parser = Session.query(MorphologicalParser).get(id)
            directory = parser.directory
            archive_dir = os.path.join(directory, 'archive')
            if os.path.exists(archive_dir):
                rmtree(archive_dir)
            os.mkdir(archive_dir)
            parser.copy_files(archive_dir)
            parser.phonology.copy_files(archive_dir)
            parser.morphology.copy_files(archive_dir)
            parser.language_model.copy_files(archive_dir)
            lib_path = os.path.join(config['here'], 'onlinelinguisticdatabase', 'lib')
            simplelm_path = os.path.join(lib_path, 'simplelm')
            parser_path = os.path.join(lib_path, 'parser.py')
            parse_path = os.path.join(lib_path, 'parse.py')
            new_parse_path = os.path.join(archive_dir, 'parse.py')
            copytree(simplelm_path, os.path.join(archive_dir, 'simplelm'))
            copyfile(parser_path, os.path.join(archive_dir, 'parser.py'))
            copyfile(parse_path, new_parse_path)
            os.chmod(new_parse_path, 0744)
            data = parser.export()
            data_path = os.path.join(archive_dir, 'data.pickle')
            cPickle.dump(data, open(data_path, 'wb'))
            zip_path = h.zipdir(archive_dir)
            return forward(FileApp(zip_path))
        except Exception, e:
            log.warn(e)
            response.status_int = 400
            return json.dumps({'error': 'An error occured while attempting to export '
                               'morphological parser %s' % id})

    @h.restrict('GET')
    @h.authenticate_with_JSON
    @h.authorize(['administrator', 'contributor'])
    def export(self, id):
        """Export the parser as a self-contained .zip archive including a Python interface and all required files.

        This allows a user to use the parser locally (assuming they have foma and MITLM installed) via
        the following procedure:

            $ unzip archive.zip
            $ cd archive
            $ ./parse.py chiens chats tombait

        """
        try:
            parser = Session.query(MorphologicalParser).get(id)
            directory = parser.directory
            lib_path = os.path.abspath(os.path.dirname(h.__file__))

            # config.pickle is a dict used to construct the parser (see lib/parse.py)
            config_ = parser.export()
            config_path = os.path.join(directory, 'config.pickle')
            cPickle.dump(config_, open(config_path, 'wb'))

            # cache.pickle is a dict encoding the cached parses of this parser
            cache_dict = parser.cache.export()
            cache_path = os.path.join(directory, 'cache.pickle')
            cPickle.dump(cache_dict, open(cache_path, 'wb'))

            # create the .zip archive, including the files of the parser, the simplelm package,
            # the parser.py module and the parse.py executable.
            zip_path = os.path.join(directory, 'archive.zip')
            zip_file = h.ZipFile(zip_path, 'w')
            #zip_file.write_directory(parser.directory)
            for file_name in os.listdir(directory):
                if (os.path.splitext(file_name)[1] not in ('.log', '.sh', '.zip') and
                    file_name != 'morpheme_language_model.pickle'):
                    zip_file.write_file(os.path.join(directory, file_name))
            zip_file.write_directory(os.path.join(lib_path, 'simplelm'), keep_dir=True)
            zip_file.write_file(os.path.join(lib_path, 'parser.py'))
            zip_file.write_file(os.path.join(lib_path, 'parse.py'))
            zip_file.close()
            return forward(FileApp(zip_path))
        except Exception, e:
            log.warn(e)
            response.status_int = 400
            return json.dumps({'error': 'An error occured while attempting to export '
                'morphological parser %s: %s' % (id, e)})

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
    morphological_parser = MorphologicalParser(
        parent_directory = h.get_OLD_directory_path('morphologicalparsers', config=config),
        UUID = unicode(uuid4()),
        name = h.normalize(data['name']),
        description = h.normalize(data['description']),
        enterer = session['user'],
        modifier = session['user'],
        datetime_modified = h.now(),
        datetime_entered = h.now(),
        phonology = data['phonology'],
        morphology = data['morphology'],
        language_model = data['language_model']
    )
    return morphological_parser

def update_morphological_parser(morphological_parser, data):
    """Update a morphological parser.

    :param morphological_parser: the morphological parser model to be updated.
    :param dict data: representation of the updated morphological parser.
    :returns: the updated morphological parser model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = morphological_parser.set_attr('name', h.normalize(data['name']), changed)
    changed = morphological_parser.set_attr('description', h.normalize(data['description']), changed)
    changed = morphological_parser.set_attr('phonology', data['phonology'], changed)
    changed = morphological_parser.set_attr('morphology', data['morphology'], changed)
    changed = morphological_parser.set_attr('language_model', data['language_model'], changed)
    if changed:
        session['user'] = Session.merge(session['user'])
        morphological_parser.modifier = session['user']
        morphological_parser.datetime_modified = h.now()
        return morphological_parser
    return changed

def generate_and_compile_morphological_parser(morphological_parser_id, compile_=True):
    morphological_parser = Session.query(MorphologicalParser).get(morphological_parser_id)
    if not morphological_parser:
        response.status_int = 404
        return {'error': 'There is no morphological parser with id %s' % id}
    if compile_ and not h.foma_installed():
        response.status_int = 400
        return {'error': 'Foma and flookup are not installed.'}
    foma_worker_q.put({
        'id': h.generate_salt(),
        'func': 'generate_and_compile_parser',
        'args': {
            'morphological_parser_id': morphological_parser.id,
            'compile': compile_,
            'user_id': session['user'].id,
            'timeout': h.morphological_parser_compile_timeout
        }
    })
    return morphological_parser

