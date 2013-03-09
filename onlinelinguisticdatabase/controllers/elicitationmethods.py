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
import re
import simplejson as json

from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import ElicitationMethodSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
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

    queryBuilder = SQLAQueryBuilder('ElicitationMethod', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all elicitation method resources.

        :URL: ``GET /elicitationmethods`` with optional query string parameters
            for ordering and pagination.
        :returns: a list of all elicitation method resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(ElicitationMethod)
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
        """Create a new elicitation method resource and return it.

        :URL: ``POST /elicitationmethods``
        :request body: JSON object representing the elicitation method to create.
        :returns: the newly created elicitation method.

        """
        try:
            schema = ElicitationMethodSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
            elicitationMethod = createNewElicitationMethod(result)
            Session.add(elicitationMethod)
            Session.commit()
            return elicitationMethod
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
        elicitationMethod = Session.query(ElicitationMethod).get(int(id))
        if elicitationMethod:
            try:
                schema = ElicitationMethodSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                elicitationMethod = updateElicitationMethod(elicitationMethod, data)
                # elicitationMethod will be False if there are no changes (cf. updateElicitationMethod).
                if elicitationMethod:
                    Session.add(elicitationMethod)
                    Session.commit()
                    return elicitationMethod
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
        elicitationMethod = Session.query(ElicitationMethod).get(id)
        if elicitationMethod:
            Session.delete(elicitationMethod)
            Session.commit()
            return elicitationMethod
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
        elicitationMethod = Session.query(ElicitationMethod).get(id)
        if elicitationMethod:
            return elicitationMethod
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

                {"elicitationMethod": {...}, "data": {...}}

            where the value of the ``elicitationMethod`` key is a dictionary
            representation of the elicitation method and the value of the
            ``data`` key is a dictionary containing the objects necessary to
            update an elicitation method, viz. ``{}``.

        """
        elicitationMethod = Session.query(ElicitationMethod).get(id)
        if elicitationMethod:
            return {'data': {}, 'elicitationMethod': elicitationMethod}
        else:
            response.status_int = 404
            return {'error': 'There is no elicitation method with id %s' % id}


################################################################################
# ElicitationMethod Create & Update Functions
################################################################################

def createNewElicitationMethod(data):
    """Create a new elicitation method.

    :param dict data: the elicitation method to be created.
    :returns: an SQLAlchemy model object representing the elicitation method.

    """
    elicitationMethod = ElicitationMethod()
    elicitationMethod.name = h.normalize(data['name'])
    elicitationMethod.description = h.normalize(data['description'])
    elicitationMethod.datetimeModified = datetime.datetime.utcnow()
    return elicitationMethod

def updateElicitationMethod(elicitationMethod, data):
    """Update an elicitation method.

    :param elicitationMethod: the elicitation method model to be updated.
    :param dict data: representation of the updated elicitation method.
    :returns: the updated elicitation method model or, if ``changed`` has not
        been set to ``True``, ``False``.

    """
    changed = False
    changed = h.setAttr(elicitationMethod, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(elicitationMethod, 'description', h.normalize(data['description']), changed)
    if changed:
        elicitationMethod.datetimeModified = datetime.datetime.utcnow()
        return elicitationMethod
    return changed
