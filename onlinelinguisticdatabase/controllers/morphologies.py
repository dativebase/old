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
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import MorphologySchema, MorphemeSequencesSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
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

    TODO: consider generating values for ``lexicon_script`` and ``rules_script`` attributes
    which, by default, are concatenated to produce a value for the ``script`` attribute but 
    where such default auto-generation can be overridden by the user so that, for example, the
    auto-generated subscripts could be used to hand-write a more intelligent morphology FST script.

    """

    query_builder = SQLAQueryBuilder('Morphology', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of morphology resources matching the input JSON
        query.

        :URL: ``SEARCH /morphologies`` (or ``POST /morphologies/search``)
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
        """Return the data necessary to search the morphology resources.

        :URL: ``GET /morphologies/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all morphology resources.

        :URL: ``GET /morphologies`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all morphology resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_morphology(Session.query(Morphology))
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
            morphology.make_directory_safely(morphology.directory)
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
        return get_data_for_new_edit(dict(request.GET))

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
        morphology = h.eagerload_morphology(Session.query(Morphology)).get(int(id))
        if morphology:
            try:
                schema = MorphologySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                morphology_dict = morphology.get_dict()
                morphology = update_morphology(morphology, data)
                # morphology will be False if there are no changes (cf. update_morphology).
                if morphology:
                    backup_morphology(morphology_dict)
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
        morphology = h.eagerload_morphology(Session.query(Morphology)).get(id)
        if morphology:
            morphology_dict = morphology.get_dict()
            backup_morphology(morphology_dict)
            Session.delete(morphology)
            Session.commit()
            morphology.remove_directory()
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
        :GET param str lexicon: if set to '1', the lexicon (dict) will be returned with the morphology
        :returns: a morphology model object.

        """
        morphology = h.eagerload_morphology(Session.query(Morphology)).get(id)
        if morphology:
            morphology_dict = morphology.get_dict()
            if request.GET.get('script') == u'1':
                morphology_script_path = morphology.get_file_path('script')
                if os.path.isfile(morphology_script_path):
                    morphology_dict['script'] = codecs.open(morphology_script_path, mode='r', encoding='utf8').read()
                else:
                    morphology_dict['script'] = u''
            if request.GET.get('lexicon') == u'1':
                morphology_lexicon_path = morphology.get_file_path('lexicon')
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
            is a list of corpora in the database.

        """
        morphology = h.eagerload_morphology(Session.query(Morphology)).get(id)
        if morphology:
            return {'data': get_data_for_new_edit(dict(request.GET)), 'morphology': morphology}
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

                {"morphology": { ... }, "previous_versions": [ ... ]}

            where the value of the ``morphology`` key is the morphology whose
            history is requested and the value of the ``previous_versions`` key
            is a list of dictionaries representing previous versions of the
            morphology.

        """
        morphology, previous_versions = h.get_model_and_previous_versions('Morphology', id)
        if morphology or previous_versions:
            return {'morphology': morphology,
                    'previous_versions': previous_versions}
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
    @h.authenticate_with_JSON
    def servecompiled(self, id):
        """Serve the compiled foma script of the morphology.

        :URL: ``PUT /morphologies/servecompiled/id``
        :param str id: the ``id`` value of a morphology.
        :returns: a stream of bytes -- the compiled morphology script.  

        """
        morphology = Session.query(Morphology).get(id)
        if morphology:
            if h.foma_installed():
                foma_file_path = morphology.get_file_path('binary')
                if os.path.isfile(foma_file_path):
                    return forward(FileApp(foma_file_path))
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
            if h.foma_installed():
                morphology_binary_path = morphology.get_file_path('binary')
                if os.path.isfile(morphology_binary_path):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        inputs = MorphemeSequencesSchema.to_python(inputs)
                        inputs = [h.normalize(i) for i in inputs['morpheme_sequences']]
                        return morphology.apply(direction, inputs)
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

        
def get_data_for_new_edit(GET_params):
    """Return the data needed to create a new morphology or edit one."""
    model_name_map = {'corpora': 'Corpus'}
    getter_map = {'corpora': h.get_mini_dicts_getter('Corpus')}
    return h.get_data_for_new_action(GET_params, getter_map, model_name_map)

################################################################################
# Backup morphology
################################################################################

def backup_morphology(morphology_dict):
    """Backup a morphology.

    :param dict morphology_dict: a representation of a morphology model.
    :returns: ``None``

    """
    morphology_backup = MorphologyBackup()
    morphology_backup.vivify(morphology_dict)
    Session.add(morphology_backup)


################################################################################
# Morphology Create & Update Functions
################################################################################

def create_new_morphology(data):
    """Create a new morphology.

    :param dict data: the data for the morphology to be created.
    :returns: an SQLAlchemy model object representing the morphology.

    """
    morphology = Morphology(
        parent_directory = h.get_OLD_directory_path('morphologies', config=config),
        word_boundary_symbol = h.word_boundary_symbol,
        morpheme_delimiters = h.get_morpheme_delimiters(type_=u'unicode'),
        rare_delimiter = h.rare_delimiter,
        UUID = unicode(uuid4()),
        name = h.normalize(data['name']),
        description = h.normalize(data['description']),
        enterer = session['user'],
        modifier = session['user'],
        datetime_modified = h.now(),
        datetime_entered = h.now(),
        lexicon_corpus = data['lexicon_corpus'],
        rules_corpus = data['rules_corpus'],
        script_type = data['script_type'],
        extract_morphemes_from_rules_corpus = data['extract_morphemes_from_rules_corpus'],
        rules = data['rules'],
        rich_upper = data['rich_upper'],
        rich_lower = data['rich_lower'],
        include_unknowns = data['include_unknowns']
    )
    return morphology

def update_morphology(morphology, data):
    """Update a morphology.

    :param morphology: the morphology model to be updated.
    :param dict data: representation of the updated morphology.
    :returns: the updated morphology model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = morphology.set_attr('name', h.normalize(data['name']), changed)
    changed = morphology.set_attr('description', h.normalize(data['description']), changed)
    changed = morphology.set_attr('lexicon_corpus', data['lexicon_corpus'], changed)
    changed = morphology.set_attr('rules_corpus', data['rules_corpus'], changed)
    changed = morphology.set_attr('script_type', data['script_type'], changed)
    changed = morphology.set_attr('extract_morphemes_from_rules_corpus', data['extract_morphemes_from_rules_corpus'], changed)
    changed = morphology.set_attr('rules', data['rules'], changed)
    changed = morphology.set_attr('rich_upper', data['rich_upper'], changed)
    changed = morphology.set_attr('rich_lower', data['rich_lower'], changed)
    changed = morphology.set_attr('include_unknowns', data['include_unknowns'], changed)
    changed = morphology.set_attr('rare_delimiter', h.rare_delimiter, changed)
    changed = morphology.set_attr('word_boundary_symbol', h.word_boundary_symbol, changed)
    if changed:
        session['user'] = Session.merge(session['user'])
        morphology.modifier = session['user']
        morphology.datetime_modified = h.now()
        return morphology
    return changed

def generate_and_compile_morphology(morphology_id, compile_=True):
    morphology = Session.query(Morphology).get(morphology_id)
    if not morphology:
        response.status_int = 404
        return {'error': 'There is no morphology with id %s' % id}
    if compile_ and not h.foma_installed():
        response.status_int = 400
        return {'error': 'Foma and flookup are not installed.'}
    foma_worker_q.put({
        'id': h.generate_salt(),
        'func': 'generate_and_compile_morphology',
        'args': {
            'morphology_id': morphology.id,
            'compile': compile_,
            'user_id': session['user'].id,
            'timeout': h.morphology_compile_timeout
        }
    })
    return morphology

