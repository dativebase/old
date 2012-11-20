import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class LanguagesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('language', 'languages')

    def index(self, format='html'):
        """GET /languages: All items in the collection"""
        # url('languages')

    def create(self):
        """POST /languages: Create a new item"""
        # url('languages')

    def new(self, format='html'):
        """GET /languages/new: Form to create a new item"""
        # url('new_language')

    def update(self, id):
        """PUT /languages/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('language', id=ID),
        #           method='put')
        # url('language', id=ID)

    def delete(self, id):
        """DELETE /languages/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('language', id=ID),
        #           method='delete')
        # url('language', id=ID)

    def show(self, id, format='html'):
        """GET /languages/id: Show a specific item"""
        # url('language', id=ID)

    def edit(self, id, format='html'):
        """GET /languages/id/edit: Form to edit an existing item"""
        # url('edit_language', id=ID)
