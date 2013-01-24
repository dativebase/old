import logging
import datetime
import re
import simplejson as json

from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from old.lib.base import BaseController
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import CollectionBackup

log = logging.getLogger(__name__)

class CollectionbackupsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol

    Collection backups are created when updating and deleting collections; they
    cannot be created directly and they should never be deleted.  This
    controller facilitates searching and getting of collection backups only.
    """

    queryBuilder = SQLAQueryBuilder('CollectionBackup', config=config)

    @h.OLDjsonify
    @restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """SEARCH /collectionbackups: Return all collection backups matching the filter passed as JSON in the request body.
        Note: POST /collectionbackups/search also routes to this action. The request body must be
        a JSON object with a 'query' attribute; a 'paginator' attribute is
        optional.  The 'query' object is passed to the getSQLAQuery() method of
        an SQLAQueryBuilder instance and an SQLA query is returned or an error
        is raised.  The 'query' object requires a 'filter' attribute; an
        'orderBy' attribute is optional.
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

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def new_search(self):
        """GET /collectionbackups/new_search: Return the data necessary to inform a search
        on the collection backups resource.
        """
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /collectionbackups: Return all collection backups."""
        try:
            query = Session.query(CollectionBackup)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels(u'CollectionBackup', query)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.OLDjsonify
    def create(self):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.OLDjsonify
    def new(self, format='html'):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.OLDjsonify
    def update(self, id):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.OLDjsonify
    def delete(self, id):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /collectionbackups/id: Return a JSON object representation of the
        collection backup with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
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

    @h.OLDjsonify
    def edit(self, id, format='html'):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}
