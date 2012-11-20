import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class OldcollectionsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('collection', 'oldcollections')

    def index(self, format='html'):
        """GET /oldcollections: All items in the collection"""
        # url('oldcollections')

    def create(self):
        """POST /oldcollections: Create a new item"""
        # url('oldcollections')

    def new(self, format='html'):
        """GET /oldcollections/new: Form to create a new item"""
        # url('new_collection')

    def update(self, id):
        """PUT /oldcollections/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('collection', id=ID),
        #           method='put')
        # url('collection', id=ID)

    def delete(self, id):
        """DELETE /oldcollections/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('collection', id=ID),
        #           method='delete')
        # url('collection', id=ID)

    def show(self, id, format='html'):
        """GET /oldcollections/id: Show a specific item"""
        # url('collection', id=ID)

    def edit(self, id, format='html'):
        """GET /oldcollections/id/edit: Form to edit an existing item"""
        # url('edit_collection', id=ID)
