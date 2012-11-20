import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class CollectionfilesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('collectionfile', 'collectionfiles')

    def index(self, format='html'):
        """GET /collectionfiles: All items in the collection"""
        # url('collectionfiles')

    def create(self):
        """POST /collectionfiles: Create a new item"""
        # url('collectionfiles')

    def new(self, format='html'):
        """GET /collectionfiles/new: Form to create a new item"""
        # url('new_collectionfile')

    def update(self, id):
        """PUT /collectionfiles/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('collectionfile', id=ID),
        #           method='put')
        # url('collectionfile', id=ID)

    def delete(self, id):
        """DELETE /collectionfiles/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('collectionfile', id=ID),
        #           method='delete')
        # url('collectionfile', id=ID)

    def show(self, id, format='html'):
        """GET /collectionfiles/id: Show a specific item"""
        # url('collectionfile', id=ID)

    def edit(self, id, format='html'):
        """GET /collectionfiles/id/edit: Form to edit an existing item"""
        # url('edit_collectionfile', id=ID)
