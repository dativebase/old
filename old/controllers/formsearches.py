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
from old.lib.schemata import FormSearchSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import FormSearch

log = logging.getLogger(__name__)

class FormsearchesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('FormSearch', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """SEARCH /formsearches: Return all form searches matching the filter passed as JSON in
        the request body.  Note: POST /formsearches/search also routes to this action.
        The request body must be a JSON object with a 'query' attribute; a
        'paginator' attribute is optional.  The 'query' object is passed to the
        getSQLAQuery() method of an SQLAQueryBuilder instance and an SQLA query
        is returned or an error is raised.  The 'query' object requires a
        'filter' attribute; an 'orderBy' attribute is optional.

        Yes, that's right, you can search form searches.  Can you search searches
        of form searches?  No, not yet...
        """
        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            query = h.eagerloadFormSearch(
                self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query')))
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

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """GET /formsearches/new_search: Return the data necessary to inform a search
        on the form searches resource.
        """
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /formsearches: Return all form searches."""
        try:
            query = h.eagerloadFormSearch(Session.query(FormSearch))
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
        """POST /formsearches: Create a new form search."""
        try:
            schema = FormSearchSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.getStateObject(values)
            state.config = config
            data = schema.to_python(values, state)
            formSearch = createNewFormSearch(data)
            Session.add(formSearch)
            Session.commit()
            return formSearch
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
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}


    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /formsearches/id: Update an existing form search."""
        formSearch = h.eagerloadFormSearch(Session.query(FormSearch)).get(int(id))
        if formSearch:
            try:
                schema = FormSearchSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                state.config = config
                data = schema.to_python(values, state)
                formSearch = updateFormSearch(formSearch, data)
                # formSearch will be False if there are no changes (cf. updateFormSearch).
                if formSearch:
                    Session.add(formSearch)
                    Session.commit()
                    return formSearch
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
        """DELETE /formsearches/id: Delete an existing form search."""
        formSearch = h.eagerloadFormSearch(Session.query(FormSearch)).get(id)
        if formSearch:
            Session.delete(formSearch)
            Session.commit()
            return formSearch
        else:
            response.status_int = 404
            return {'error': 'There is no form search with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /formsearches/id: Return a JSON object representation of the formsearch with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """
        formSearch = h.eagerloadFormSearch(Session.query(FormSearch)).get(id)
        if formSearch:
            return formSearch
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
        formSearch = h.eagerloadFormSearch(Session.query(FormSearch)).get(id)
        if formSearch:
            data = {'searchParameters': h.getSearchParameters(self.queryBuilder)}
            return {'data': data, 'formSearch': formSearch}
        else:
            response.status_int = 404
            return {'error': 'There is no form search with id %s' % id}


################################################################################
# FormSearch Create & Update Functions
################################################################################

def createNewFormSearch(data):
    """Create a new form search model object given a data dictionary
    provided by the user (as a JSON object).
    """

    formSearch = FormSearch()
    formSearch.name = h.normalize(data['name'])
    formSearch.search = data['search']      # Note that this is purposefully not normalized (reconsider this? ...)
    formSearch.description = h.normalize(data['description'])
    formSearch.enterer = session['user']
    formSearch.datetimeModified = datetime.datetime.utcnow()
    return formSearch

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updateFormSearch function
# below.
CHANGED = None

def updateFormSearch(formSearch, data):
    """Update the input form  search model object given a data dictionary
    provided by the user (as a JSON object).  If CHANGED is not set to true in
    the course of attribute setting, then None is returned and no update occurs.
    """

    global CHANGED

    def setAttr(obj, name, value):
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            global CHANGED
            CHANGED = True

    # Unicode Data
    setAttr(formSearch, 'name', h.normalize(data['name']))
    setAttr(formSearch, 'search', data['search'])
    setAttr(formSearch, 'description', h.normalize(data['description']))

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        formSearch.datetimeModified = datetime.datetime.utcnow()
        return formSearch
    return CHANGED