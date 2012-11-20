import logging

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to

from old.lib.base import BaseController, render

log = logging.getLogger(__name__)

class SpeakersController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('speaker', 'speakers')

    def index(self, format='html'):
        """GET /speakers: All items in the collection"""
        # url('speakers')

    def create(self):
        """POST /speakers: Create a new item"""
        # url('speakers')

    def new(self, format='html'):
        """GET /speakers/new: Form to create a new item"""
        # url('new_speaker')

    def update(self, id):
        """PUT /speakers/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('speaker', id=ID),
        #           method='put')
        # url('speaker', id=ID)

    def delete(self, id):
        """DELETE /speakers/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('speaker', id=ID),
        #           method='delete')
        # url('speaker', id=ID)

    def show(self, id, format='html'):
        """GET /speakers/id: Show a specific item"""
        # url('speaker', id=ID)

    def edit(self, id, format='html'):
        """GET /speakers/id/edit: Form to edit an existing item"""
        # url('edit_speaker', id=ID)
