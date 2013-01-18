import logging
import datetime
import re
import simplejson as json

from pylons import request, response, session, app_globals
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from old.lib.base import BaseController
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Language

log = logging.getLogger(__name__)

class LanguagesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol

    The language table is populated from an ISO 639-3 file upon application setup.
    The Language resouces is read-only.  This controller facilitates searching
    and getting of languages only.
    """

    queryBuilder = SQLAQueryBuilder('Language', 'Id')

    @restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """SEARCH /languages: Return all languages matching the filter passed as JSON in the request body.
        Note: POST /languages/search also routes to this action. The request body must be
        a JSON object with a 'query' attribute; a 'paginator' attribute is
        optional.  The 'query' object is passed to the getSQLAQuery() method of
        an SQLAQueryBuilder instance and an SQLA query is returned or an error
        is raised.  The 'query' object requires a 'filter' attribute; an
        'orderBy' attribute is optional.
        """

        response.content_type = 'application/json'
        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            SQLAQuery = self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query'))
            result = h.addPagination(SQLAQuery, pythonSearchParams.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return json.dumps({'errors': e.unpack_errors()})
        # SQLAQueryBuilder should have captured these exceptions (and packed
        # them into an OLDSearchParseError) or sidestepped them, but here we'll
        # handle any that got past -- just in case.
        except (OperationalError, AttributeError, InvalidRequestError, RuntimeError):
            response.status_int = 400
            return json.dumps({'error':
                u'The specified search parameters generated an invalid database query'})
        else:
            return json.dumps(result, cls=h.JSONOLDEncoder)

    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /languages: Return all languages."""

        response.content_type = 'application/json'
        try:
            query = Session.query(Language)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder, 'Id')
            result = h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return json.dumps({'errors': e.unpack_errors()})
        else:
            return json.dumps(result, cls=h.JSONOLDEncoder)

    def create(self):
        response.content_type = 'application/json'
        response.status_int = 404
        return json.dumps({'error': 'This resource is read-only.'})

    def new(self, format='html'):
        response.content_type = 'application/json'
        response.status_int = 404
        return json.dumps({'error': 'This resource is read-only.'})

    def update(self, id):
        response.content_type = 'application/json'
        response.status_int = 404
        return json.dumps({'error': 'This resource is read-only.'})

    def delete(self, id):
        response.content_type = 'application/json'
        response.status_int = 404
        return json.dumps({'error': 'This resource is read-only.'})

    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /languages/id: Return a JSON object representation of the
        language with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """

        response.content_type = 'application/json'
        language = Session.query(Language).get(id)
        if language:
            result = json.dumps(language, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no language with Id %s' % id})
        return result

    def edit(self, id, format='html'):
        response.content_type = 'application/json'
        response.status_int = 404
        return json.dumps({'error': 'This resource is read-only.'})
