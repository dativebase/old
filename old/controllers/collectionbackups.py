import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class CollectionbackupsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('collectionbackup', 'collectionbackups')

    def index(self, format='html'):
        """GET /collectionbackups: All items in the collection"""
        # url('collectionbackups')

    def create(self):
        """POST /collectionbackups: Create a new item"""
        # url('collectionbackups')

    def new(self, format='html'):
        """GET /collectionbackups/new: Form to create a new item"""
        # url('new_collectionbackup')

    def update(self, id):
        """PUT /collectionbackups/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('collectionbackup', id=ID),
        #           method='put')
        # url('collectionbackup', id=ID)

    def delete(self, id):
        """DELETE /collectionbackups/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('collectionbackup', id=ID),
        #           method='delete')
        # url('collectionbackup', id=ID)

    def show(self, id, format='html'):
        """GET /collectionbackups/id: Show a specific item"""
        # url('collectionbackup', id=ID)

    def edit(self, id, format='html'):
        """GET /collectionbackups/id/edit: Form to edit an existing item"""
        # url('edit_collectionbackup', id=ID)
