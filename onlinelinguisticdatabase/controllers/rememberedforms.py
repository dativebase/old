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

"""Contains the :class:`RememberedformsController` and its auxiliary functions.

.. module:: rememberedforms
   :synopsis: Contains the remembered forms controller and its auxiliary functions.

"""

import logging
import datetime
import re
import simplejson as json
from uuid import uuid4

from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc
from sqlalchemy.orm import subqueryload
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import FormIdsSchemaNullable
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Form, User

log = logging.getLogger(__name__)

class RememberedformsController(BaseController):
    """Generate responses to requests on remembered forms resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
        Remembered forms is a pseudo-REST-ful resource.  Remembered forms are
        stored in the ``userform`` many-to-many table (cf. ``model/user.py``)
        which defines the contents of a user's ``rememberedForms`` attribute
        (as well as the contents of a form's ``memorizers`` attribute). A user's
        remembered forms are not affected by requests to the user resource.
        Instead, the remembered forms resource handles modification, retrieval
        and search of a user's remembered forms.

        Overview of the interface:

        * ``GET /rememberedforms/id``
        * ``UPDATE /rememberedforms/id``
        * ``SEARCH /rememberedforms/id``

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder(config=config)

    @h.jsonify
    @h.authenticate
    @h.restrict('GET')
    def show(self, id):
        """Return a user's remembered forms.
        
        :URL: ``GET /rememberedforms/id`` with optional query string parameters
            for ordering and pagination.
        :param str id: the ``id`` value of a user model.
        :returns: a list form models.

        .. note::

            Any authenticated user is authorized to access this resource.
            Restricted forms are filtered from the array on a per-user basis.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        user = Session.query(User).get(id)
        if user:
            try:
                query = h.eagerloadForm(Session.query(Form))\
                            .filter(Form.memorizers.contains(user))
                query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
                query = h.filterRestrictedModels('Form', query)
                return h.addPagination(query, dict(request.GET))
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}

    @h.jsonify
    @h.authenticate
    @h.restrict('PUT')
    @h.authorize(['administrator', 'contributor', 'viewer'], None, True)
    def update(self, id):
        """Update a user's remembered forms and return them.

        :URL: ``PUT /rememberedforms/id``
        :Request body: JSON object of the form ``{"forms": [...]}`` where the
            array contains the form ``id`` values that will constitute the
            user's ``rememberedForms`` collection after update.
        :param str id: the ``id`` value of the user model whose
            ``rememberedForms`` attribute is to be updated.
        :returns: the list of remembered forms of the user.

        .. note::

            Administrators can update any user's remembered forms;
            non-administrators can only update their own.

        """
        user = Session.query(User).options(subqueryload(User.rememberedForms)).get(id)
        if user:
            try:
                schema = FormIdsSchemaNullable
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                forms = [f for f in data['forms'] if f]
                accessible = h.userIsAuthorizedToAccessModel
                unrestrictedUsers = h.getUnrestrictedUsers()
                unrestrictedForms = [f for f in forms
                                     if accessible(user, f, unrestrictedUsers)]
                if set(user.rememberedForms) != set(unrestrictedForms):
                    user.rememberedForms = unrestrictedForms
                    user.datetimeModified = h.now()
                    Session.commit()
                    return user.rememberedForms
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
            return {'error': 'There is no user with id %s' % id}

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self, id):
        """Return the remembered forms of a user that match the input JSON query.

        :URL: ``SEARCH /rememberedforms/id`` (or ``POST /rememberedforms/id/search``).
        :param str id: the ``id`` value of the user whose remembered forms are searched.
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "orderBy": [ ... ]},
                 "paginator": { ... }}

            where the ``orderBy`` and ``paginator`` attributes are optional.

        """
        user = Session.query(User).get(id)
        if user:
            try:
                jsonSearchParams = unicode(request.body, request.charset)
                pythonSearchParams = json.loads(jsonSearchParams)
                query = h.eagerloadForm(
                    self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query')))
                query = query.filter(Form.memorizers.contains(user))
                query = h.filterRestrictedModels('Form', query)
                return h.addPagination(query, pythonSearchParams.get('paginator'))
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except (OLDSearchParseError, Invalid), e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
            except:
                response.status_int = 400
                return {'error': u'The specified search parameters generated an invalid database query'}
        else:
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}
