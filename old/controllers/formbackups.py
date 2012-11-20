import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class FormbackupsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('formbackup', 'formbackups')

    def index(self, format='html'):
        """GET /formbackups: All items in the collection"""
        # url('formbackups')

    def create(self):
        """POST /formbackups: Create a new item"""
        # url('formbackups')

    def new(self, format='html'):
        """GET /formbackups/new: Form to create a new item"""
        # url('new_formbackup')

    def update(self, id):
        """PUT /formbackups/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('formbackup', id=ID),
        #           method='put')
        # url('formbackup', id=ID)

    def delete(self, id):
        """DELETE /formbackups/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('formbackup', id=ID),
        #           method='delete')
        # url('formbackup', id=ID)

    def show(self, id, format='html'):
        """GET /formbackups/id: Show a specific item"""
        # url('formbackup', id=ID)

    def edit(self, id, format='html'):
        """GET /formbackups/id/edit: Form to edit an existing item"""
        # url('edit_formbackup', id=ID)
