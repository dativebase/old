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
from old.lib.schemata import PageSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Page

log = logging.getLogger(__name__)

class PagesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Page')

    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /pages: Return all pages."""
        response.content_type = 'application/json'
        try:
            query = Session.query(Page)
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
        """POST /pages: Create a new page."""
        response.content_type = 'application/json'
        try:
            schema = PageSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
        except h.JSONDecodeError:
            response.status_int = 400
            result = h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            result = json.dumps({'errors': e.unpack_errors()})
        else:
            page = createNewPage(result)
            Session.add(page)
            Session.commit()
            result = json.dumps(page, cls=h.JSONOLDEncoder)
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """GET /pages/new: Return the data necessary to create a new OLD
        page.
        """

        response.content_type = 'application/json'
        return json.dumps({'markupLanguages': h.markupLanguages})

    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /pages/id: Update an existing page."""

        response.content_type = 'application/json'
        page = Session.query(Page).get(int(id))
        if page:
            try:
                schema = PageSchema()
                values = json.loads(unicode(request.body, request.charset))
                result = schema.to_python(values)
            except h.JSONDecodeError:
                response.status_int = 400
                result = h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                result = json.dumps({'errors': e.unpack_errors()})
            else:
                page = updatePage(page, result)
                # page will be False if there are no changes (cf. updatePage).
                if page:
                    Session.add(page)
                    Session.commit()
                    result = json.dumps(page, cls=h.JSONOLDEncoder)
                else:
                    response.status_int = 400
                    result = json.dumps({'error': u''.join([
                        u'The update request failed because the submitted ',
                        u'data were not new.'])})
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no page with id %s' % id})
        return result

    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /pages/id: Delete an existing page."""

        response.content_type = 'application/json'
        page = Session.query(Page).get(id)
        if page:
            Session.delete(page)
            Session.commit()
            result = json.dumps(page, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no page with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /pages/id: Return a JSON object representation of the page with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """

        response.content_type = 'application/json'
        page = Session.query(Page).get(id)
        if page:
            result = json.dumps(page, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no page with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /pages/id/edit: Return the data necessary to update an existing
        OLD page; here we return only the page and
        an empty JSON object.
        """

        response.content_type = 'application/json'
        page = Session.query(Page).get(id)
        if page:
            result = {'data': {'markupLanguages': h.markupLanguages}, 'page': page}
            result = json.dumps(result, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no page with id %s' % id})
        return result


################################################################################
# Page Create & Update Functions
################################################################################

def createNewPage(data):
    """Create a new page model object given a data dictionary
    provided by the user (as a JSON object).
    """

    page = Page()
    page.name = h.normalize(data['name'])
    page.heading = h.normalize(data['heading'])
    page.markupLanguage = data['markupLanguage']
    page.content = h.normalize(data['content'])
    page.html = h.getHTMLFromContents(page.content, page.markupLanguage)
    page.datetimeModified = datetime.datetime.utcnow()
    return page

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updatePage function
# below.
CHANGED = None

def updatePage(page, data):
    """Update the input page model object given a data dictionary
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
    setAttr(page, 'name', h.normalize(data['name']))
    setAttr(page, 'heading', h.normalize(data['heading']))
    setAttr(page, 'markupLanguage', data['markupLanguage'])
    setAttr(page, 'content', h.normalize(data['content']))
    setAttr(page, 'html', h.getHTMLFromContents(page.content, page.markupLanguage))

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        page.datetimeModified = datetime.datetime.utcnow()
        return page
    return CHANGED