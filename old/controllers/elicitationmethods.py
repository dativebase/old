import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class ElicitationmethodsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('elicitationmethod', 'elicitationmethods')

    def index(self, format='html'):
        """GET /elicitationmethods: All items in the collection"""
        # url('elicitationmethods')

    def create(self):
        """POST /elicitationmethods: Create a new item"""
        # url('elicitationmethods')

    def new(self, format='html'):
        """GET /elicitationmethods/new: Form to create a new item"""
        # url('new_elicitationmethod')

    def update(self, id):
        """PUT /elicitationmethods/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('elicitationmethod', id=ID),
        #           method='put')
        # url('elicitationmethod', id=ID)

    def delete(self, id):
        """DELETE /elicitationmethods/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('elicitationmethod', id=ID),
        #           method='delete')
        # url('elicitationmethod', id=ID)

    def show(self, id, format='html'):
        """GET /elicitationmethods/id: Show a specific item"""
        # url('elicitationmethod', id=ID)

    def edit(self, id, format='html'):
        """GET /elicitationmethods/id/edit: Form to edit an existing item"""
        # url('edit_elicitationmethod', id=ID)
