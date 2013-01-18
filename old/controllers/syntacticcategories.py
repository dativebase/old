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
from old.lib.schemata import SyntacticCategorySchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import SyntacticCategory

log = logging.getLogger(__name__)

class SyntacticcategoriesController(BaseController):

    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('SyntacticCategory')

    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /syntacticcategories: Return all syntactic categories."""
        response.content_type = 'application/json'
        try:
            query = Session.query(SyntacticCategory)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            result = h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return json.dumps({'errors': e.unpack_errors()})
        else:
            return json.dumps(result, cls=h.JSONOLDEncoder)

    @restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """POST /syntacticcategories: Create a new syntactic category."""
        response.content_type = 'application/json'
        try:
            schema = SyntacticCategorySchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
        except h.JSONDecodeError:
            response.status_int = 400
            result = h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            result = json.dumps({'errors': e.unpack_errors()})
        else:
            syntacticCategory = createNewSyntacticCategory(result)
            Session.add(syntacticCategory)
            Session.commit()
            result = json.dumps(syntacticCategory, cls=h.JSONOLDEncoder)
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """GET /syntacticcategories/new: Return the data necessary to create a new OLD
        syntactic category.  Here we simply return the list of syntactic category
        types defined in lib/utils.
        """

        response.content_type = 'application/json'
        return json.dumps({'syntacticCategoryTypes': h.syntacticCategoryTypes})

    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /syntacticcategories/id: Update an existing syntactic category."""

        response.content_type = 'application/json'
        syntacticCategory = Session.query(SyntacticCategory).get(int(id))
        if syntacticCategory:
            try:
                schema = SyntacticCategorySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                result = schema.to_python(values, state)
            except h.JSONDecodeError:
                response.status_int = 400
                result = h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                result = json.dumps({'errors': e.unpack_errors()})
            else:
                syntacticCategory = updateSyntacticCategory(syntacticCategory, result)
                # syntacticCategory will be False if there are no changes (cf. updateSyntacticCategory).
                if syntacticCategory:
                    Session.add(syntacticCategory)
                    Session.commit()
                    result = json.dumps(syntacticCategory, cls=h.JSONOLDEncoder)
                else:
                    response.status_int = 400
                    result = json.dumps({'error': u''.join([
                        u'The update request failed because the submitted ',
                        u'data were not new.'])})
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no syntactic category with id %s' % id})
        return result

    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /syntacticcategories/id: Delete an existing syntactic category."""

        response.content_type = 'application/json'
        syntacticCategory = Session.query(SyntacticCategory).get(id)
        if syntacticCategory:
            Session.delete(syntacticCategory)
            Session.commit()
            result = json.dumps(syntacticCategory, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no syntactic category with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /syntacticcategories/id: Return a JSON object representation of
        the syntactic category with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """

        response.content_type = 'application/json'
        syntacticCategory = Session.query(SyntacticCategory).get(id)
        if syntacticCategory:
            result = json.dumps(syntacticCategory, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no syntactic category with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /syntacticcategories/id/edit: Return the data necessary to update an existing
        OLD syntactic category; here we return only the syntactic category and
        the list of syntactic category types defined in lib/utils.
        """

        response.content_type = 'application/json'
        syntacticCategory = Session.query(SyntacticCategory).get(id)
        if syntacticCategory:
            result = {
                'data': {'syntacticCategoryTypes': h.syntacticCategoryTypes},
                'syntacticCategory': syntacticCategory
            }
            result = json.dumps(result, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no syntactic category with id %s' % id})
        return result


################################################################################
# SyntacticCategory Create & Update Functions
################################################################################

def createNewSyntacticCategory(data):
    """Create a new syntactic category model object given a data dictionary
    provided by the user (as a JSON object).
    """

    syntacticCategory = SyntacticCategory()
    syntacticCategory.name = h.normalize(data['name'])
    syntacticCategory.type = h.normalize(data['type'])
    syntacticCategory.description = h.normalize(data['description'])
    syntacticCategory.datetimeModified = datetime.datetime.utcnow()
    return syntacticCategory

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updateSyntacticCategory function
# below.
CHANGED = None

def updateSyntacticCategory(syntacticCategory, data):
    """Update the input syntactic category model object given a data dictionary
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
    setAttr(syntacticCategory, 'name', h.normalize(data['name']))
    setAttr(syntacticCategory, 'type', h.normalize(data['type']))
    setAttr(syntacticCategory, 'description', h.normalize(data['description']))

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        syntacticCategory.datetimeModified = datetime.datetime.utcnow()
        return syntacticCategory
    return CHANGED