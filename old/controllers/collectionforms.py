import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class CollectionformsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('collectionform', 'collectionforms')

    def index(self, format='html'):
        """GET /collectionforms: All items in the collection"""
        # url('collectionforms')

    def create(self):
        """POST /collectionforms: Create a new item"""
        # url('collectionforms')

    def new(self, format='html'):
        """GET /collectionforms/new: Form to create a new item"""
        # url('new_collectionform')

    def update(self, id):
        """PUT /collectionforms/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('collectionform', id=ID),
        #           method='put')
        # url('collectionform', id=ID)

    def delete(self, id):
        """DELETE /collectionforms/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('collectionform', id=ID),
        #           method='delete')
        # url('collectionform', id=ID)

    def show(self, id, format='html'):
        """GET /collectionforms/id: Show a specific item"""
        # url('collectionform', id=ID)

    def edit(self, id, format='html'):
        """GET /collectionforms/id/edit: Form to edit an existing item"""
        # url('edit_collectionform', id=ID)
