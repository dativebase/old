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
from old.lib.schemata import OrthographySchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Orthography

log = logging.getLogger(__name__)

class OrthographiesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Orthography')

    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /orthographies: Return all orthographies."""
        response.content_type = 'application/json'
        try:
            query = Session.query(Orthography)
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
        """POST /orthographies: Create a new orthography."""
        response.content_type = 'application/json'
        try:
            schema = OrthographySchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
        except h.JSONDecodeError:
            response.status_int = 400
            result = h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            result = json.dumps({'errors': e.unpack_errors()})
        else:
            orthography = createNewOrthography(result)
            Session.add(orthography)
            Session.commit()
            result = json.dumps(orthography, cls=h.JSONOLDEncoder)
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """GET /orthographies/new: Return the data necessary to create a new OLD
        orthography.  NOTHING TO RETURN HERE ...
        """

        response.content_type = 'application/json'
        return json.dumps({})

    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /orthographies/id: Update an existing orthography."""

        response.content_type = 'application/json'
        orthography = Session.query(Orthography).get(int(id))
        if orthography:
            try:
                schema = OrthographySchema()
                values = json.loads(unicode(request.body, request.charset))
                result = schema.to_python(values)
            except h.JSONDecodeError:
                response.status_int = 400
                result = h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                result = json.dumps({'errors': e.unpack_errors()})
            else:
                orthography = updateOrthography(orthography, result)
                # orthography will be False if there are no changes (cf. updateOrthography).
                if orthography:
                    Session.add(orthography)
                    Session.commit()
                    result = json.dumps(orthography, cls=h.JSONOLDEncoder)
                else:
                    response.status_int = 400
                    result = json.dumps({'error': u''.join([
                        u'The update request failed because the submitted ',
                        u'data were not new.'])})
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no orthography with id %s' % id})
        return result

    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /orthographies/id: Delete an existing orthography."""

        response.content_type = 'application/json'
        orthography = Session.query(Orthography).get(id)
        if orthography:
            Session.delete(orthography)
            Session.commit()
            result = json.dumps(orthography, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no orthography with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /orthographies/id: Return a JSON object representation of the orthography with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """

        response.content_type = 'application/json'
        orthography = Session.query(Orthography).get(id)
        if orthography:
            result = json.dumps(orthography, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no orthography with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /orthographies/id/edit: Return the data necessary to update an existing
        OLD orthography; here we return only the orthography and
        an empty JSON object.
        """

        response.content_type = 'application/json'
        orthography = Session.query(Orthography).get(id)
        if orthography:
            result = {'data': {}, 'orthography': orthography}
            result = json.dumps(result, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no orthography with id %s' % id})
        return result


################################################################################
# Orthography Create & Update Functions
################################################################################

def createNewOrthography(data):
    """Create a new orthography model object given a data dictionary
    provided by the user (as a JSON object).
    """

    orthography = Orthography()
    orthography.name = h.normalize(data['name'])
    orthography.orthography = h.normalize(data['orthography'])
    orthography.lowercase = data['lowercase']
    orthography.initialGlottalStops = data['initialGlottalStops']
    orthography.datetimeModified = datetime.datetime.utcnow()
    return orthography

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updateOrthography function
# below.
CHANGED = None

def updateOrthography(orthography, data):
    """Update the input orthography model object given a data dictionary
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
    setAttr(orthography, 'name', h.normalize(data['name']))
    setAttr(orthography, 'orthography', h.normalize(data['orthography']))
    setAttr(orthography, 'lowercase', data['lowercase'])
    setAttr(orthography, 'initialGlottalStops', data['initialGlottalStops'])
    
    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        orthography.datetimeModified = datetime.datetime.utcnow()
        return orthography
    return CHANGED