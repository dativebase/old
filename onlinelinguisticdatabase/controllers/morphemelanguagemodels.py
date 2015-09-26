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

"""Contains the :class:`MorphemelanguagemodelsController` and its auxiliary functions.

.. module:: morphemelanguagemodels
   :synopsis: Contains the morpheme language models controller and its auxiliary functions.

TODO: write tests for REST parts of parsers
TODO: permit choice of morpheme vs category-based language models

"""

import logging
import simplejson as json
import os
from uuid import uuid4
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import MorphemeLanguageModelSchema, MorphemeSequencesSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import MorphemeLanguageModel, MorphemeLanguageModelBackup
from onlinelinguisticdatabase.lib.foma_worker import foma_worker_q

log = logging.getLogger(__name__)

class MorphemelanguagemodelsController(BaseController):
    """Generate responses to requests on morpheme language model resources.

    A morpheme language model is a function that computes probabilities for sequences of morphemes.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::

       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('MorphemeLanguageModel', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of morpheme language model resources matching the
        input JSON query.

        :URL: ``SEARCH /morphemelanguagemodels`` (or ``POST
            /morphemelanguagemodels/search``)
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
        """Return the data necessary to search the morpheme language model
        resources.

        :URL: ``GET /morphemelanguagemodels/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all morpheme language model resources.

        :URL: ``GET /morphemelanguagemodels`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all morpheme language model resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_morpheme_language_model(Session.query(MorphemeLanguageModel))
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
        """Create a new morpheme language model resource and return it.

        :URL: ``POST /morphemelanguagemodels``
        :request body: JSON object representing the morpheme language model to create.
        :returns: the newly created morpheme language model.

        """
        try:
            schema = MorphemeLanguageModelSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            lm = create_new_morpheme_language_model(data)
            Session.add(lm)
            Session.commit()
            lm.make_directory_safely(lm.directory)
            return lm
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
        """Return the data necessary to create a new morpheme language model.

        :URL: ``GET /morphemelanguagemodels/new``.
        :returns: a dictionary containing ...

        """
        return get_data_for_new_edit(dict(request.GET))

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a morpheme language model and return it.

        :URL: ``PUT /morphemelanguagemodels/id``
        :Request body: JSON object representing the morpheme language model with updated attribute values.
        :param str id: the ``id`` value of the morpheme language model to be updated.
        :returns: the updated morpheme language model model.

        """
        morpheme_language_model = h.eagerload_morpheme_language_model(Session.query(MorphemeLanguageModel)).get(int(id))
        if morpheme_language_model:
            try:
                schema = MorphemeLanguageModelSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                morpheme_language_model_dict = morpheme_language_model.get_dict()
                morpheme_language_model = update_morpheme_language_model(morpheme_language_model, data)
                # morpheme_language_model will be False if there are no changes (cf. update_morpheme_language_model).
                if morpheme_language_model:
                    backup_morpheme_language_model(morpheme_language_model_dict)
                    Session.add(morpheme_language_model)
                    Session.commit()
                    return morpheme_language_model
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
            return {'error': 'There is no morpheme language model with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing morpheme language model and return it.

        :URL: ``DELETE /morphemelanguagemodels/id``
        :param str id: the ``id`` value of the morpheme language model to be deleted.
        :returns: the deleted morpheme language model model.

        """
        lm = h.eagerload_morpheme_language_model(Session.query(MorphemeLanguageModel)).get(id)
        if lm:
            lm_dict = lm.get_dict()
            backup_morpheme_language_model(lm_dict)
            Session.delete(lm)
            Session.commit()
            lm.remove_directory()
            return lm
        else:
            response.status_int = 404
            return {'error': 'There is no morpheme language model with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a morpheme language model.

        :URL: ``GET /morphemelanguagemodels/id``
        :param str id: the ``id`` value of the morpheme language model to be returned.
        :returns: a morpheme language model model object.

        """
        lm = h.eagerload_morpheme_language_model(Session.query(MorphemeLanguageModel)).get(id)
        if lm:
            return lm
        else:
            response.status_int = 404
            return {'error': 'There is no morpheme language model with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a morpheme language model and the data needed to update it.

        :URL: ``GET /morphemelanguagemodels/id/edit``
        :param str id: the ``id`` value of the morpheme language model that will be updated.
        :returns: a dictionary of the form::

                {"morpheme_language_model": {...}, "data": {...}}

            where the value of the ``morpheme_language_model`` key is a dictionary
            representation of the morpheme_language_model and the value of the ``data`` key
            is the data structure returned by the ``new`` action.

        """
        lm = h.eagerload_morpheme_language_model(Session.query(MorphemeLanguageModel)).get(id)
        if lm:
            return {'data': get_data_for_new_edit(dict(request.GET)),
                    'morpheme_language_model': lm}
        else:
            response.status_int = 404
            return {'error': 'There is no morpheme language model with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the morpheme language model with ``morpheme_language_model.id==id`` and its previous versions.

        :URL: ``GET /morphemelanguagemodels/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            morpheme language model whose history is requested.
        :returns: A dictionary of the form::

                {"morpheme_language_model": { ... }, "previous_versions": [ ... ]}

            where the value of the ``morpheme_language_model`` key is the morpheme language model whose
            history is requested and the value of the ``previous_versions`` key
            is a list of dictionaries representing previous versions of the
            morpheme language model.

        """
        lm, previous_versions = h.get_model_and_previous_versions('MorphemeLanguageModel', id)
        if lm or previous_versions:
            return {'morpheme_language_model': lm,
                    'previous_versions': previous_versions}
        else:
            response.status_int = 404
            return {'error': 'No morpheme language models or morpheme language model backups match %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def generate(self, id):
        """Generate the files that constitute the morpheme language model, crucially the file that holds the pickled LM trie.

        :URL: ``PUT /morpheme_language_model/id/generate``
        :param str id: the ``id`` value of the morpheme language model whose files will be generated.
        :returns: the morpheme language model is returned;  ``GET /morpheme_language_model/id`` must be polled to
            determine when the generation task has terminated.

        """
        lm = Session.query(MorphemeLanguageModel).get(id)
        if not lm:
            response.status_int = 404
            return {'error': 'There is no morpheme language model with id %s' % id}
        args = {
            'morpheme_language_model_id': lm.id,
            'user_id': session['user'].id,
            'timeout': h.morpheme_language_model_generate_timeout
        }
        foma_worker_q.put({
            'id': h.generate_salt(),
            'func': 'generate_language_model',
            'args': args
        })
        return lm

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def get_probabilities(self, id):
        """Return the probability of each sequence of morphemes passed in the JSON PUT params.

        :param list morpheme_sequences: space-delimited morphemes in form|gloss|category
            format wherer "|" is actually ``h.rare_delimiter``.
        :returns: a dictionary with morpheme sequences as keys and log probabilities as values.

        """
        lm = Session.query(MorphemeLanguageModel).get(id)
        if lm:
            try:
                schema = MorphemeSequencesSchema()
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                morpheme_sequences = [h.normalize(ms) for ms in data['morpheme_sequences']]
                return lm.get_probabilities(morpheme_sequences)
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
            except Exception:
                response.status_int = 400
                return {'error': 'An error occurred while trying to generate probabilities.'}
        else:
            response.status_int = 404
            return {'error': 'There is no morpheme language model with id %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def compute_perplexity(self, id):
        """Compute the perplexity of the LM's corpus according to the LM.

        Randomly divide the corpus into training and test sets multiple times and compute
        the perplexity and return the average.  See ``evaluate_morpheme_language_model`` in lib/foma_worker.py.

        """
        lm = Session.query(MorphemeLanguageModel).get(id)
        if not lm:
            response.status_int = 404
            return {'error': 'There is no morpheme language model with id %s' % id}
        args = {
            'morpheme_language_model_id': lm.id,
            'user_id': session['user'].id,
            'timeout': h.morpheme_language_model_generate_timeout
        }
        foma_worker_q.put({
            'id': h.generate_salt(),
            'func': 'compute_perplexity',
            'args': args
        })
        return lm

    @h.restrict('GET')
    @h.authenticate_with_JSON
    def serve_arpa(self, id):
        """Serve the generated ARPA file of the morpheme language model.

        :URL: ``PUT /morphemelanguagemodels/serve_arpa/id``
        :param str id: the ``id`` value of a morpheme language model.
        :returns: a stream of bytes -- the ARPA file of the LM.

        """
        lm = Session.query(MorphemeLanguageModel).get(id)
        if lm:
            arpa_path = lm.get_file_path('arpa')
            if os.path.isfile(arpa_path):
                if authorized_to_access_arpa_file(session['user'], lm):
                    return forward(FileApp(arpa_path, content_type='text/plain'))
                else:
                    response.status_int = 403
                    return json.dumps(h.unauthorized_msg)
            else:
                response.status_int = 404
                return json.dumps({'error':
                    'The ARPA file for morpheme language model %s has not been compiled yet.' % id})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no morpheme language model with id %s' % id})

def authorized_to_access_arpa_file(user, morpheme_language_model):
    """Return True if user is authorized to access the ARPA file of the morpheme LM."""
    if (morpheme_language_model.restricted and user.role != u'administrator' and
    user not in h.get_unrestricted_users()):
        return False
    return True

def get_data_for_new_edit(GET_params):
    """Return the data needed to create a new morpheme language model or edit one."""
    model_name_map = {'corpora': 'Corpus', 'morphologies': 'Morphology'}
    getter_map = {
        'corpora': h.get_mini_dicts_getter('Corpus'),
        'morphologies': h.get_mini_dicts_getter('Morphology'),
        'toolkits': lambda: h.language_model_toolkits
    }
    mandatory_attributes = ['toolkits']
    return h.get_data_for_new_action(GET_params, getter_map, model_name_map, mandatory_attributes)

################################################################################
# Backup morpheme_language_model
################################################################################

def backup_morpheme_language_model(morpheme_language_model_dict):
    """Backup a morpheme language model.

    :param dict morpheme_language_model_dict: a representation of a morpheme language model model.
    :returns: ``None``

    """
    morpheme_language_model_backup = MorphemeLanguageModelBackup()
    morpheme_language_model_backup.vivify(morpheme_language_model_dict)
    Session.add(morpheme_language_model_backup)

################################################################################
# MorphemeLanguageModel Create & Update Functions
################################################################################

def create_new_morpheme_language_model(data):
    """Create a new morpheme language model.

    :param dict data: the data for the morpheme language model to be created.
    :returns: an SQLAlchemy model object representing the morpheme language model.

    """
    morpheme_language_model = MorphemeLanguageModel(
        parent_directory = h.get_OLD_directory_path('morphemelanguagemodels', config=config),
        rare_delimiter = h.rare_delimiter,
        start_symbol = h.lm_start,
        end_symbol = h.lm_end,
        morpheme_delimiters = h.get_morpheme_delimiters(type_=u'unicode'),
        UUID = unicode(uuid4()),
        name = h.normalize(data['name']),
        description = h.normalize(data['description']),
        enterer = session['user'],
        modifier = session['user'],
        datetime_modified = h.now(),
        datetime_entered = h.now(),
        vocabulary_morphology = data['vocabulary_morphology'],
        corpus = data['corpus'],
        toolkit = data['toolkit'],
        order = data['order'],
        smoothing = data['smoothing'],
        categorial = data['categorial']
    )
    return morpheme_language_model

def update_morpheme_language_model(morpheme_language_model, data):
    """Update a morpheme language model.

    :param morpheme_language_model: the morpheme language model model to be updated.
    :param dict data: representation of the updated morpheme language model.
    :returns: the updated morpheme language model model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = morpheme_language_model.set_attr('name', h.normalize(data['name']), changed)
    changed = morpheme_language_model.set_attr('description', h.normalize(data['description']), changed)
    changed = morpheme_language_model.set_attr('vocabulary_morphology', data['vocabulary_morphology'], changed)
    changed = morpheme_language_model.set_attr('corpus', data['corpus'], changed)
    changed = morpheme_language_model.set_attr('toolkit', data['toolkit'], changed)
    changed = morpheme_language_model.set_attr('order', data['order'], changed)
    changed = morpheme_language_model.set_attr('smoothing', data['smoothing'], changed)
    changed = morpheme_language_model.set_attr('categorial', data['categorial'], changed)
    changed = morpheme_language_model.set_attr('rare_delimiter', h.rare_delimiter, changed)
    changed = morpheme_language_model.set_attr('start_symbol', h.lm_start, changed)
    changed = morpheme_language_model.set_attr('end_symbol', h.lm_end, changed)
    if changed:
        session['user'] = Session.merge(session['user'])
        morpheme_language_model.modifier = session['user']
        morpheme_language_model.datetime_modified = h.now()
        return morpheme_language_model
    return changed

