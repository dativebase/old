# Copyright 2013 Joel Dunham
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Contains the :class:`CorporaController` and its auxiliary functions.

.. module:: corpora
   :synopsis: Contains the corpora controller and its auxiliary functions.

"""

import logging
import datetime
import re
import os
from uuid import uuid4
import simplejson as json
from string import letters, digits
from random import sample
from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from pylons.controllers.util import forward
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import CorpusSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Corpus, CorpusBackup

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
