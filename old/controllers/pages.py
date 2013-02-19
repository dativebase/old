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
from old.lib.schemata import PageSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Page

log = logging.getLogger(__name__)

class PagesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Page', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /pages: Return all pages."""
        try:
            query = Session.query(Page)
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
        """POST /pages: Create a new page."""
        try:
            schema = PageSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            page = createNewPage(data)
            Session.add(page)
            Session.commit()
            return page
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
        """GET /pages/new: Return the data necessary to create a new OLD
        page.
        """
        return {'markupLanguages': h.markupLanguages}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /pages/id: Update an existing page."""
        page = Session.query(Page).get(int(id))
        if page:
            try:
                schema = PageSchema()
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                page = updatePage(page, data)
                # page will be False if there are no changes (cf. updatePage).
                if page:
                    Session.add(page)
                    Session.commit()
                    return page
                else:
                    response.status_int = 400
                    return {'error':
                        u'The update request failed because the submitted data were not new.'}
            except h.JSONDecodeError:
                response.status_int = 400
                return  h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no page with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /pages/id: Delete an existing page."""
        page = Session.query(Page).get(id)
        if page:
            Session.delete(page)
            Session.commit()
            return page
        else:
            response.status_int = 404
            return {'error': 'There is no page with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /pages/id: Return a JSON object representation of the page with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """
        page = Session.query(Page).get(id)
        if page:
            return page
        else:
            response.status_int = 404
            return {'error': 'There is no page with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /pages/id/edit: Return the data necessary to update an existing
        OLD page; here we return only the page and
        an empty JSON object.
        """
        page = Session.query(Page).get(id)
        if page:
            return {'data': {'markupLanguages': h.markupLanguages}, 'page': page}
        else:
            response.status_int = 404
            return {'error': 'There is no page with id %s' % id}


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

def updatePage(page, data):
    """Update the input page model object given a data dictionary
    provided by the user (as a JSON object).  If changed is not set to true in
    the course of attribute setting, then None is returned and no update occurs.
    """
    changed = False
    # Unicode Data
    changed = h.setAttr(page, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(page, 'heading', h.normalize(data['heading']), changed)
    changed = h.setAttr(page, 'markupLanguage', data['markupLanguage'], changed)
    changed = h.setAttr(page, 'content', h.normalize(data['content']), changed)
    changed = h.setAttr(page, 'html', h.getHTMLFromContents(page.content, page.markupLanguage), changed)

    if changed:
        page.datetimeModified = datetime.datetime.utcnow()
        return page
    return changed