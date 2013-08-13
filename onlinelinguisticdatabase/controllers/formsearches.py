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

"""Contains the :class:`FormsearchesController`.

.. module:: formsearches
   :synopsis: Contains the form searches controller.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import FormSearchSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import FormSearch

log = logging.getLogger(__name__)

class FormsearchesController(BaseController):
    """Generate responses to requests on form search resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('FormSearch', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of form search resources matching the input JSON query.

        :URL: ``SEARCH /formsearches`` (or ``POST /formsearches/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        .. note::
        
            Yes, that's right, you can search form searches.  (No, you can't
            search searches of form searches :)

        """
        try:
            json_search_params = unicode(request.body, request.charset)
            python_search_params = json.loads(json_search_params)
            query = h.eagerload_form_search(
                self.query_builder.get_SQLA_query(python_search_params.get('query')))
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
        """Return the data necessary to search the form search resources.

        :URL: ``GET /formsearches/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all form search resources.

        :URL: ``GET /formsearches`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all form search resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_form_search(Session.query(FormSearch))
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
        """Create a new form search resource and return it.

        :URL: ``POST /formsearches``
        :request body: JSON object representing the form search to create.
        :returns: the newly created form search.

        """
        try:
            schema = FormSearchSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.get_state_object(values)
            state.config = config
            data = schema.to_python(values, state)
            form_search = create_new_form_search(data)
            Session.add(form_search)
            Session.commit()
            return form_search
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
        """GET /formsearches/new: Return the data necessary to create a new OLD
        form search.
        """
        """Return the data necessary to create a new form search.

        :URL: ``GET /formsearches/new`` with optional query string parameters 
        :returns: A dictionary of lists of resources

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}


    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a form search and return it.
        
        :URL: ``PUT /formsearches/id``
        :Request body: JSON object representing the form search with updated
            attribute values.
        :param str id: the ``id`` value of the form search to be updated.
        :returns: the updated form search model.

        """
        form_search = h.eagerload_form_search(Session.query(FormSearch)).get(int(id))
        if form_search:
            try:
                schema = FormSearchSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                state.config = config
                data = schema.to_python(values, state)
                form_search = update_form_search(form_search, data)
                # form_search will be False if there are no changes (cf. update_form_search).
                if form_search:
                    Session.add(form_search)
                    Session.commit()
                    return form_search
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
            return {'error': 'There is no form search with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing form search and return it.

        :URL: ``DELETE /formsearches/id``
        :param str id: the ``id`` value of the form search to be deleted.
        :returns: the deleted form search model.

        """

        form_search = h.eagerload_form_search(Session.query(FormSearch)).get(id)
        if form_search:
            Session.delete(form_search)
            Session.commit()
            return form_search
        else:
            response.status_int = 404
            return {'error': 'There is no form search with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a form search.

        :URL: ``GET /formsearches/id``
        :param str id: the ``id`` value of the form search to be returned.
        :returns: a form search model object.

        """
        form_search = h.eagerload_form_search(Session.query(FormSearch)).get(id)
        if form_search:
            return form_search
        else:
            response.status_int = 404
            return {'error': 'There is no form search with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /formsearches/id/edit: Return the data necessary to update an existing
        OLD form search.
        """
        """Return a form search and the data needed to update it.

        :URL: ``GET /formsearches/edit`` with optional query string parameters 
        :param str id: the ``id`` value of the form search that will be updated.
        :returns: a dictionary of the form::

                {"form_search": {...}, "data": {...}}

            where the value of the ``form_search`` key is a dictionary
            representation of the form search and the value of the ``data`` key
            is a dictionary containing the data necessary to update a form
            search.

        """
        form_search = h.eagerload_form_search(Session.query(FormSearch)).get(id)
        if form_search:
            data = {'search_parameters': h.get_search_parameters(self.query_builder)}
            return {'data': data, 'form_search': form_search}
        else:
            response.status_int = 404
            return {'error': 'There is no form search with id %s' % id}


################################################################################
# FormSearch Create & Update Functions
################################################################################

def create_new_form_search(data):
    """Create a new form search.

    :param dict data: the form search to be created.
    :returns: an form search model object.

    """

    form_search = FormSearch()
    form_search.name = h.normalize(data['name'])
    form_search.search = data['search']      # Note that this is purposefully not normalized (reconsider this? ...)
    form_search.description = h.normalize(data['description'])
    form_search.enterer = session['user']
    form_search.datetime_modified = datetime.datetime.utcnow()
    return form_search

def update_form_search(form_search, data):
    """Update a form search model.

    :param form: the form search model to be updated.
    :param dict data: representation of the updated form search.
    :returns: the updated form search model or, if ``changed`` has not been set
        to ``True``, then ``False``.

    """

    changed = False

    # Unicode Data
    changed = form_search.set_attr('name', h.normalize(data['name']), changed)
    changed = form_search.set_attr('search', data['search'], changed)
    changed = form_search.set_attr('description', h.normalize(data['description']), changed)

    if changed:
        form_search.datetime_modified = datetime.datetime.utcnow()
        return form_search
    return changed
