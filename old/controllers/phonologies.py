import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class PhonologiesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('phonology', 'phonologies')

    def index(self, format='html'):
        """GET /phonologies: All items in the collection"""
        # url('phonologies')

    def create(self):
        """POST /phonologies: Create a new item"""
        # url('phonologies')

    def new(self, format='html'):
        """GET /phonologies/new: Form to create a new item"""
        # url('new_phonology')

    def update(self, id):
        """PUT /phonologies/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('phonology', id=ID),
        #           method='put')
        # url('phonology', id=ID)

    def delete(self, id):
        """DELETE /phonologies/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('phonology', id=ID),
        #           method='delete')
        # url('phonology', id=ID)

    def show(self, id, format='html'):
        """GET /phonologies/id: Show a specific item"""
        # url('phonology', id=ID)

    def edit(self, id, format='html'):
        """GET /phonologies/id/edit: Form to edit an existing item"""
        # url('edit_phonology', id=ID)
