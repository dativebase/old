import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class FormfilesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('formfile', 'formfiles')

    def index(self, format='html'):
        """GET /formfiles: All items in the collection"""
        # url('formfiles')

    def create(self):
        """POST /formfiles: Create a new item"""
        # url('formfiles')

    def new(self, format='html'):
        """GET /formfiles/new: Form to create a new item"""
        # url('new_formfile')

    def update(self, id):
        """PUT /formfiles/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('formfile', id=ID),
        #           method='put')
        # url('formfile', id=ID)

    def delete(self, id):
        """DELETE /formfiles/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('formfile', id=ID),
        #           method='delete')
        # url('formfile', id=ID)

    def show(self, id, format='html'):
        """GET /formfiles/id: Show a specific item"""
        # url('formfile', id=ID)

    def edit(self, id, format='html'):
        """GET /formfiles/id/edit: Form to edit an existing item"""
        # url('edit_formfile', id=ID)
