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
import simplejson as json
import os
from uuid import uuid4
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import PhonologySchema, MorphophonemicTranscriptionsSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Phonology, PhonologyBackup
from onlinelinguisticdatabase.lib.foma_worker import foma_worker_q

log = logging.getLogger(__name__)

class PhonologiesController(BaseController):
    """Generate responses to requests on phonology resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::

       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('Phonology', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of phonology resources matching the input JSON
        query.

        :URL: ``SEARCH /phonologies`` (or ``POST /phonologies/search``)
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
        """Return the data necessary to search the phonology resources.

        :URL: ``GET /phonologies/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all phonology resources.

        :URL: ``GET /phonologies`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all phonology resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_phonology(Session.query(Phonology))
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
        """Create a new phonology resource and return it.

        :URL: ``POST /phonologies``
        :request body: JSON object representing the phonology to create.
        :returns: the newly created phonology.

        """
        try:
            schema = PhonologySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            phonology = create_new_phonology(data)
            Session.add(phonology)
            Session.commit()
            phonology.save_script(decombine=True) # ``decombine`` means separate unicode combining characters from their bases
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
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(int(id))
        if phonology:
            try:
                schema = PhonologySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                phonology_dict = phonology.get_dict()
                phonology = update_phonology(phonology, data)
                # phonology will be False if there are no changes (cf. update_phonology).
                if phonology:
                    backup_phonology(phonology_dict)
                    Session.add(phonology)
                    Session.commit()
                    phonology.save_script()
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
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(id)
        if phonology:
            phonology_dict = phonology.get_dict()
            backup_phonology(phonology_dict)
            Session.delete(phonology)
            Session.commit()
            phonology.remove_directory()
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
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(id)
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
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(id)
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

                {"phonology": { ... }, "previous_versions": [ ... ]}

            where the value of the ``phonology`` key is the phonology whose
            history is requested and the value of the ``previous_versions`` key
            is a list of dictionaries representing previous versions of the
            phonology.

        """
        phonology, previous_versions = h.get_model_and_previous_versions('Phonology', id)
        if phonology or previous_versions:
            return {'phonology': phonology,
                    'previous_versions': previous_versions}
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
            :mod:`onlinelinguisticdatabase.lib.foma_worker`.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.foma_installed():
                foma_worker_q.put({
                    'id': h.generate_salt(),
                    'func': 'compile_phonology',
                    'args': {
                        'phonology_id': phonology.id,
                        'user_id': session['user'].id,
                        'timeout': h.phonology_compile_timeout
                    }
                })
                return phonology
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.restrict('GET')
    @h.authenticate_with_JSON
    def servecompiled(self, id):
        """Serve the compiled foma script of the phonology.

        :URL: ``PUT /phonologies/servecompiled/id``
        :param str id: the ``id`` value of a phonology.
        :returns: a stream of bytes -- the compiled phonology script.  

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.foma_installed():
                compiled_path = phonology.get_file_path('binary')
                if os.path.isfile(compiled_path):
                    return forward(FileApp(compiled_path))
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'Phonology %d has not been compiled yet.' % phonology.id})
            else:
                response.status_int = 400
                return json.dumps({'error': 'Foma and flookup are not installed.'})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no phonology with id %s' % id})

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
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
            if h.foma_installed():
                binary_path = phonology.get_file_path('binary')
                if os.path.isfile(binary_path):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        inputs = MorphophonemicTranscriptionsSchema.to_python(inputs)
                        inputs = [h.normalize(i) for i in inputs['transcriptions']]
                        return phonology.applydown(inputs)
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
            if h.foma_installed():
                try:
                    test_results = phonology.run_tests()
                    if test_results:
                        return test_results
                    else:
                        response.status_int = 400
                        return {'error': 'The script of phonology %d contains no tests.' % phonology.id}
                except AttributeError:
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

def backup_phonology(phonology_dict):
    """Backup a phonology.

    :param dict phonology_dict: a representation of a phonology model.
    :returns: ``None``

    """
    phonology_backup = PhonologyBackup()
    phonology_backup.vivify(phonology_dict)
    Session.add(phonology_backup)


################################################################################
# Phonology Create & Update Functions
################################################################################

def create_new_phonology(data):
    """Create a new phonology.

    :param dict data: the data for the phonology to be created.
    :returns: an SQLAlchemy model object representing the phonology.

    """
    phonology = Phonology(
        parent_directory = h.get_OLD_directory_path('phonologies', config=config),
        word_boundary_symbol = h.word_boundary_symbol,
        UUID = unicode(uuid4()),
        name = h.normalize(data['name']),
        description = h.normalize(data['description']),
        script = h.normalize(data['script']).replace(u'\r', u''),  # normalize or not?
        enterer = session['user'],
        modifier = session['user'],
        datetime_modified = h.now(),
        datetime_entered = h.now()
    )
    return phonology

def update_phonology(phonology, data):
    """Update a phonology.

    :param page: the phonology model to be updated.
    :param dict data: representation of the updated phonology.
    :returns: the updated phonology model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = phonology.set_attr('name', h.normalize(data['name']), changed)
    changed = phonology.set_attr('description', h.normalize(data['description']), changed)
    changed = phonology.set_attr('script', h.normalize(data['script']), changed)
    changed = phonology.set_attr('word_boundary_symbol', h.word_boundary_symbol, changed)

    if changed:
        session['user'] = Session.merge(session['user'])
        phonology.modifier = session['user']
        phonology.datetime_modified = h.now()
        return phonology
    return changed

