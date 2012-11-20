import logging

from pylons import request, response, session

from old.lib.base import BaseController

log = logging.getLogger(__name__)

class FilesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""
    # To properly map this controller, ensure your config/routing.py
    # file has a resource setup:
    #     map.resource('file', 'files')

    def index(self):
        """GET /files: All items in the collection"""
        # url('files')
        return 'IN FILES'

    def create(self):
        """POST /files: Create a new item"""
        # url('files')

    def new(self, format='html'):
        """GET /files/new: Form to create a new item"""
        # url('new_file')

    def update(self, id):
        """PUT /files/id: Update an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="PUT" />
        # Or using helpers:
        #    h.form(url('file', id=ID),
        #           method='put')
        # url('file', id=ID)

    def delete(self, id):
        """DELETE /files/id: Delete an existing item"""
        # Forms posted to this method should contain a hidden field:
        #    <input type="hidden" name="_method" value="DELETE" />
        # Or using helpers:
        #    h.form(url('file', id=ID),
        #           method='delete')
        # url('file', id=ID)

    def show(self, id, format='html'):
        """GET /files/id: Show a specific item"""
        # url('file', id=ID)

    def edit(self, id, format='html'):
        """GET /files/id/edit: Form to edit an existing item"""
        # url('edit_file', id=ID)
