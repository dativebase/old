import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class KeywordsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('keyword', 'keywords')

    def index(self, format='html'):
        """GET /keywords: All items in the collection"""
        # url('keywords')

    def create(self):
        """POST /keywords: Create a new item"""
        # url('keywords')

    def new(self, format='html'):
        """GET /keywords/new: Form to create a new item"""
        # url('new_keyword')

    def update(self, id):
        """PUT /keywords/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('keyword', id=ID),
        #           method='put')
        # url('keyword', id=ID)

    def delete(self, id):
        """DELETE /keywords/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('keyword', id=ID),
        #           method='delete')
        # url('keyword', id=ID)

    def show(self, id, format='html'):
        """GET /keywords/id: Show a specific item"""
        # url('keyword', id=ID)

    def edit(self, id, format='html'):
        """GET /keywords/id/edit: Form to edit an existing item"""
        # url('edit_keyword', id=ID)
