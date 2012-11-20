import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class GlossesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('gloss', 'glosses')

    def index(self, format='html'):
        """GET /glosses: All items in the collection"""
        # url('glosses')

    def create(self):
        """POST /glosses: Create a new item"""
        # url('glosses')

    def new(self, format='html'):
        """GET /glosses/new: Form to create a new item"""
        # url('new_gloss')

    def update(self, id):
        """PUT /glosses/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('gloss', id=ID),
        #           method='put')
        # url('gloss', id=ID)

    def delete(self, id):
        """DELETE /glosses/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('gloss', id=ID),
        #           method='delete')
        # url('gloss', id=ID)

    def show(self, id, format='html'):
        """GET /glosses/id: Show a specific item"""
        # url('gloss', id=ID)

    def edit(self, id, format='html'):
        """GET /glosses/id/edit: Form to edit an existing item"""
        # url('edit_gloss', id=ID)
