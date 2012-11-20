import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class SyntacticcategoriesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('syntacticcategory', 'syntacticcategories')

    def index(self, format='html'):
        """GET /syntacticcategories: All items in the collection"""
        # url('syntacticcategories')

    def create(self):
        """POST /syntacticcategories: Create a new item"""
        # url('syntacticcategories')

    def new(self, format='html'):
        """GET /syntacticcategories/new: Form to create a new item"""
        # url('new_syntacticcategory')

    def update(self, id):
        """PUT /syntacticcategories/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('syntacticcategory', id=ID),
        #           method='put')
        # url('syntacticcategory', id=ID)

    def delete(self, id):
        """DELETE /syntacticcategories/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('syntacticcategory', id=ID),
        #           method='delete')
        # url('syntacticcategory', id=ID)

    def show(self, id, format='html'):
        """GET /syntacticcategories/id: Show a specific item"""
        # url('syntacticcategory', id=ID)

    def edit(self, id, format='html'):
        """GET /syntacticcategories/id/edit: Form to edit an existing item"""
        # url('edit_syntacticcategory', id=ID)
