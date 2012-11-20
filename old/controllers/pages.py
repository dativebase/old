import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

try:
    import json
except ImportError:
    import simplejson as json

from old.lib.base import BaseController, render
import old.model as model
import old.model.meta as meta
import old.lib.helpers as h

log = logging.getLogger(__name__)

class PagesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('page', 'pages')

    def index(self, format='html'):
        """GET /pages: All items in the collection"""
        # url('pages')
        response.headers['Content-Type'] = 'application/json'
        return json.dumps(meta.Session.query(model.Page).all(),
                          cls=h.JSONOLDEncoder)

    def home(self):
        """GET /pages/home: Page with name='home'"""
        # url('pages/home')
        response.headers['Content-Type'] = 'application/json'
        return json.dumps(meta.Session.query(model.Page).filter(
            model.Page.name==u'home').first(), cls=h.JSONOLDEncoder)

    def create(self):
        """POST /pages: Create a new item"""
        # url('pages')

    def new(self, format='html'):
        """GET /pages/new: Form to create a new item"""
        # url('new_page')

    def update(self, id):
        """PUT /pages/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('page', id=ID),
        #           method='put')
        # url('page', id=ID)

    def delete(self, id):
        """DELETE /pages/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('page', id=ID),
        #           method='delete')
        # url('page', id=ID)

    def show(self, id, format='html'):
        """GET /pages/id: Show a specific item"""
        # url('page', id=ID)
        response.headers['Content-Type'] = 'application/json'
        return json.dumps(meta.Session.query(model.Page).get(id),
                          cls=h.JSONOLDEncoder)

    def edit(self, id, format='html'):
        """GET /pages/id/edit: Form to edit an existing item"""
        # url('edit_page', id=ID)
