import logging
import datetime
import simplejson as json

from pylons import request, response, session
from pylons.decorators.rest import restrict
from formencode.validators import Invalid

from old.lib.base import BaseController
from old.lib.schemata import OrthographySchema
import old.model as model
import old.model.meta as meta
import old.lib.helpers as h

class OrthographiesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('orthography', 'orthographies')

    def index(self, format='html'):
        """GET /orthographies: All items in the collection"""
        # url('orthographies')

    def create(self):
        """POST /orthographies: Create a new item"""
        # url('orthographies')

    def new(self, format='html'):
        """GET /orthographies/new: Form to create a new item"""
        # url('new_orthography')

    def update(self, id):
        """PUT /orthographies/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('orthography', id=ID),
        #           method='put')
        # url('orthography', id=ID)

    def delete(self, id):
        """DELETE /orthographies/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('orthography', id=ID),
        #           method='delete')
        # url('orthography', id=ID)

    def show(self, id, format='html'):
        """GET /orthographies/id: Show a specific item"""
        # url('orthography', id=ID)

    def edit(self, id, format='html'):
        """GET /orthographies/id/edit: Form to edit an existing item"""
        # url('edit_orthography', id=ID)
