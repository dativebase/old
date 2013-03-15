import logging

from pylons import request, response, session, tmpl_context as c, url
from pylons.controllers.util import abort, redirect

from onlinelinguisticdatabase.lib.base import BaseController, render

log = logging.getLogger(__name__)

class CorporaController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('corpus', 'corpora')

    def index(self, format='html'):
        """GET /corpora: All items in the collection"""
        # url('corpora')

    def create(self):
        """POST /corpora: Create a new item"""
        # url('corpora')

    def new(self, format='html'):
        """GET /corpora/new: Form to create a new item"""
        # url('new_corpus')

    def update(self, id):
        """PUT /corpora/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('corpus', id=ID),
        #           method='put')
        # url('corpus', id=ID)

    def delete(self, id):
        """DELETE /corpora/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('corpus', id=ID),
        #           method='delete')
        # url('corpus', id=ID)

    def show(self, id, format='html'):
        """GET /corpora/id: Show a specific item"""
        # url('corpus', id=ID)

    def edit(self, id, format='html'):
        """GET /corpora/id/edit: Form to edit an existing item"""
        # url('edit_corpus', id=ID)
