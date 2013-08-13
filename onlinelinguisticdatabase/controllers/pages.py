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

"""Contains the :class:`PagesController` and its auxiliary functions.

.. module:: pages
   :synopsis: Contains the pages controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import PageSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Page

log = logging.getLogger(__name__)

class PagesController(BaseController):
    """Generate responses to requests on page resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('Page', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all page resources.

        :URL: ``GET /pages`` with optional query string parameters for ordering
            and pagination.
        :returns: a list of all page resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(Page)
            query = h.add_order_by(query, dict(request.GET), self.query_builder)
            return h.add_pagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """Create a new page resource and return it.

        :URL: ``POST /pages``
        :request body: JSON object representing the page to create.
        :returns: the newly created page.

        """
        try:
            schema = PageSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            page = create_new_page(data)
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
        """Return the data necessary to create a new page.

        :URL: ``GET /pages/new``.
        :returns: a dictionary containing the names of valid OLD markup languages.

        """
        return {'markup_languages': h.markup_languages}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a page and return it.
        
        :URL: ``PUT /pages/id``
        :Request body: JSON object representing the page with updated attribute values.
        :param str id: the ``id`` value of the page to be updated.
        :returns: the updated page model.

        """
        page = Session.query(Page).get(int(id))
        if page:
            try:
                schema = PageSchema()
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                page = update_page(page, data)
                # page will be False if there are no changes (cf. update_page).
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
        """Delete an existing page and return it.

        :URL: ``DELETE /pages/id``
        :param str id: the ``id`` value of the page to be deleted.
        :returns: the deleted page model.

        """
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
        """Return a page.
        
        :URL: ``GET /pages/id``
        :param str id: the ``id`` value of the page to be returned.
        :returns: a page model object.

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
        """Return a page and the data needed to update it.

        :URL: ``GET /pages/edit``
        :param str id: the ``id`` value of the page that will be updated.
        :returns: a dictionary of the form::

                {"page": {...}, "data": {...}}

            where the value of the ``page`` key is a dictionary
            representation of the page and the value of the ``data`` key
            is the list of valid markup language names.

        """
        page = Session.query(Page).get(id)
        if page:
            return {'data': {'markup_languages': h.markup_languages}, 'page': page}
        else:
            response.status_int = 404
            return {'error': 'There is no page with id %s' % id}


################################################################################
# Page Create & Update Functions
################################################################################

def create_new_page(data):
    """Create a new page.

    :param dict data: the data for the page to be created.
    :returns: an SQLAlchemy model object representing the page.

    """
    page = Page()
    page.name = h.normalize(data['name'])
    page.heading = h.normalize(data['heading'])
    page.markup_language = data['markup_language']
    page.content = h.normalize(data['content'])
    page.html = h.get_HTML_from_contents(page.content, page.markup_language)
    page.datetime_modified = datetime.datetime.utcnow()
    return page

def update_page(page, data):
    """Update a page.

    :param page: the page model to be updated.
    :param dict data: representation of the updated page.
    :returns: the updated page model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = page.set_attr('name', h.normalize(data['name']), changed)
    changed = page.set_attr('heading', h.normalize(data['heading']), changed)
    changed = page.set_attr('markup_language', data['markup_language'], changed)
    changed = page.set_attr('content', h.normalize(data['content']), changed)
    changed = page.set_attr('html', h.get_HTML_from_contents(page.content, page.markup_language), changed)

    if changed:
        page.datetime_modified = datetime.datetime.utcnow()
        return page
    return changed
