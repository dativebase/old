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

"""Contains the :class:`ElicitationmethodsController` and its auxiliary functions.

.. module:: elicitationmethods
   :synopsis: Contains the elicitation methods controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import ElicitationMethodSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import ElicitationMethod

log = logging.getLogger(__name__)

class ElicitationmethodsController(BaseController):
    """Generate responses to requests on elicitation method resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('ElicitationMethod', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all elicitation method resources.

        :URL: ``GET /elicitationmethods`` with optional query string parameters
            for ordering and pagination.
        :returns: a list of all elicitation method resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(ElicitationMethod)
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
        """Create a new elicitation method resource and return it.

        :URL: ``POST /elicitationmethods``
        :request body: JSON object representing the elicitation method to create.
        :returns: the newly created elicitation method.

        """
        try:
            schema = ElicitationMethodSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
            elicitation_method = create_new_elicitation_method(result)
            Session.add(elicitation_method)
            Session.commit()
            return elicitation_method
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
        """Return the data necessary to create a new elicitation method.

        :URL: ``GET /elicitationmethods/new``
        :returns: an empty dictionary

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update an elicitation method and return it.
        
        :URL: ``PUT /elicitationmethods/id``
        :Request body: JSON object representing the elicitation method with updated attribute values.
        :param str id: the ``id`` value of the elicitation method to be updated.
        :returns: the updated elicitation method model.

        """
        elicitation_method = Session.query(ElicitationMethod).get(int(id))
        if elicitation_method:
            try:
                schema = ElicitationMethodSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                elicitation_method = update_elicitation_method(elicitation_method, data)
                # elicitation_method will be False if there are no changes (cf. update_elicitation_method).
                if elicitation_method:
                    Session.add(elicitation_method)
                    Session.commit()
                    return elicitation_method
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
            return {'error': 'There is no elicitation method with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing elicitation method and return it.

        :URL: ``DELETE /elicitationmethods/id``
        :param str id: the ``id`` value of the elicitation method to be deleted.
        :returns: the deleted elicitation method model.

        """
        elicitation_method = Session.query(ElicitationMethod).get(id)
        if elicitation_method:
            Session.delete(elicitation_method)
            Session.commit()
            return elicitation_method
        else:
            response.status_int = 404
            return {'error': 'There is no elicitation method with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return an elicitation method.
        
        :URL: ``GET /elicitationmethods/id``
        :param str id: the ``id`` value of the elicitation method to be returned.
        :returns: an elicitation method model object.

        """
        elicitation_method = Session.query(ElicitationMethod).get(id)
        if elicitation_method:
            return elicitation_method
        else:
            response.status_int = 404
            return {'error': 'There is no elicitation method with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return an elicitation method and the data needed to update it.

        :URL: ``GET /elicitationmethods/edit`` with optional query string parameters 
        :param str id: the ``id`` value of the elicitation method that will be updated.
        :returns: a dictionary of the form::

                {"elicitation_method": {...}, "data": {...}}

            where the value of the ``elicitation_method`` key is a dictionary
            representation of the elicitation method and the value of the
            ``data`` key is a dictionary containing the objects necessary to
            update an elicitation method, viz. ``{}``.

        """
        elicitation_method = Session.query(ElicitationMethod).get(id)
        if elicitation_method:
            return {'data': {}, 'elicitation_method': elicitation_method}
        else:
            response.status_int = 404
            return {'error': 'There is no elicitation method with id %s' % id}


################################################################################
# ElicitationMethod Create & Update Functions
################################################################################

def create_new_elicitation_method(data):
    """Create a new elicitation method.

    :param dict data: the elicitation method to be created.
    :returns: an SQLAlchemy model object representing the elicitation method.

    """
    elicitation_method = ElicitationMethod()
    elicitation_method.name = h.normalize(data['name'])
    elicitation_method.description = h.normalize(data['description'])
    elicitation_method.datetime_modified = datetime.datetime.utcnow()
    return elicitation_method

def update_elicitation_method(elicitation_method, data):
    """Update an elicitation method.

    :param elicitation_method: the elicitation method model to be updated.
    :param dict data: representation of the updated elicitation method.
    :returns: the updated elicitation method model or, if ``changed`` has not
        been set to ``True``, ``False``.

    """
    changed = False
    changed = elicitation_method.set_attr('name', h.normalize(data['name']), changed)
    changed = elicitation_method.set_attr('description', h.normalize(data['description']), changed)
    if changed:
        elicitation_method.datetime_modified = datetime.datetime.utcnow()
        return elicitation_method
    return changed
