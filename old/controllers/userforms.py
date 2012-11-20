import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class UserformsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('userform', 'userforms')

    def index(self, format='html'):
        """GET /userforms: All items in the collection"""
        # url('userforms')

    def create(self):
        """POST /userforms: Create a new item"""
        # url('userforms')

    def new(self, format='html'):
        """GET /userforms/new: Form to create a new item"""
        # url('new_userform')

    def update(self, id):
        """PUT /userforms/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('userform', id=ID),
        #           method='put')
        # url('userform', id=ID)

    def delete(self, id):
        """DELETE /userforms/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('userform', id=ID),
        #           method='delete')
        # url('userform', id=ID)

    def show(self, id, format='html'):
        """GET /userforms/id: Show a specific item"""
        # url('userform', id=ID)

    def edit(self, id, format='html'):
        """GET /userforms/id/edit: Form to edit an existing item"""
        # url('edit_userform', id=ID)
