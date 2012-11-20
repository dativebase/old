import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class FormkeywordsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('formkeyword', 'formkeywords')

    def index(self, format='html'):
        """GET /formkeywords: All items in the collection"""
        # url('formkeywords')

    def create(self):
        """POST /formkeywords: Create a new item"""
        # url('formkeywords')

    def new(self, format='html'):
        """GET /formkeywords/new: Form to create a new item"""
        # url('new_formkeyword')

    def update(self, id):
        """PUT /formkeywords/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('formkeyword', id=ID),
        #           method='put')
        # url('formkeyword', id=ID)

    def delete(self, id):
        """DELETE /formkeywords/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('formkeyword', id=ID),
        #           method='delete')
        # url('formkeyword', id=ID)

    def show(self, id, format='html'):
        """GET /formkeywords/id: Show a specific item"""
        # url('formkeyword', id=ID)

    def edit(self, id, format='html'):
        """GET /formkeywords/id/edit: Form to edit an existing item"""
        # url('edit_formkeyword', id=ID)
