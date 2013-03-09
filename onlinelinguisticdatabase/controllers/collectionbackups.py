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

"""Contains the :class:`CollectionbackupsController`.

.. module:: collectionbackups
   :synopsis: Contains the collection backups controller.

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
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import CollectionBackup

log = logging.getLogger(__name__)

class CollectionbackupsController(BaseController):
    """Generate responses to requests on collection backup resources.

    REST Controller styled on the Atom Publishing Protocol.
    
    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    .. note::
    
        Collection backups are created when updating and deleting collections;
        they cannot be created directly and they should never be deleted.  This
        controller facilitates searching and getting of collection backups only.

    """

    queryBuilder = SQLAQueryBuilder('CollectionBackup', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of collection backup resources matching the input
        JSON query.

        :URL: ``SEARCH /collectionbackups`` (or ``POST /collectionbackups/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "orderBy": [ ... ]},
                 "paginator": { ... }}

            where the ``orderBy`` and ``paginator`` attributes are optional.

        """

        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            SQLAQuery = self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query'))
            query = h.filterRestrictedModels('CollectionBackup', SQLAQuery)
            return h.addPagination(query, pythonSearchParams.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        # SQLAQueryBuilder should have captured these exceptions (and packed
        # them into an OLDSearchParseError) or sidestepped them, but here we'll
        # handle any that got past -- just in case.
        except (OperationalError, AttributeError, InvalidRequestError, RuntimeError):
            response.status_int = 400
            return {'error': u'The specified search parameters generated an invalid database query'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """Return the data necessary to search the collection backup resources.

        :URL: ``GET /collectionbackups/new_search``
        :returns: ``{"searchParameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all collection backup resources.

        :URL: ``GET /collectionbackups`` 
        :returns: a list of all collection backup resources.

        """
        try:
            query = Session.query(CollectionBackup)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels(u'CollectionBackup', query)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    def create(self):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    def new(self, format='html'):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    def update(self, id):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    def delete(self, id):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a collection backup.
        
        :URL: ``GET /collectionbackups/id``
        :param str id: the ``id`` value of the collection backup to be returned.
        :returns: a collection backup model object.

        """
        collectionBackup = Session.query(CollectionBackup).get(id)
        if collectionBackup:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, collectionBackup, unrestrictedUsers):
                return collectionBackup
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no collection backup with id %s' % id}

    @h.jsonify
    def edit(self, id, format='html'):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}
