# Copyright 2016 Joel Dunham
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

"""Contains the :class:`MorphologybackupsController`.

.. module:: morphologybackups
   :synopsis: Contains the morphology backups controller.

"""

import logging
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import MorphologyBackup

log = logging.getLogger(__name__)

class MorphologybackupsController(BaseController):
    """Generate responses to requests on morphology backup resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::

       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    .. note::
    
        Morphology backups are created when updating and deleting morphologies;
        they cannot be created directly and they should never be deleted.  This
        controller facilitates retrieval of morphology backups only.

    """

    query_builder = SQLAQueryBuilder('MorphologyBackup', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all morphology backup resources.

        :URL: ``GET /morphologybackups`` 
        :returns: a list of all morphology backup resources.

        """
        try:
            query = Session.query(MorphologyBackup)
            query = h.add_order_by(query, dict(request.GET), self.query_builder)
            return h.add_pagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    def create(self):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    def new(self, format='html'):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    def update(self, id):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    def delete(self, id):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a morphology backup.

        :URL: ``GET /morphologybackups/id``
        :param str id: the ``id`` value of the morphology backup to be returned.
        :returns: a morphology backup model object.

        """
        morphology_backup = Session.query(MorphologyBackup).get(id)
        if morphology_backup:
            return morphology_backup
        else:
            response.status_int = 404
            return {'error': 'There is no morphology backup with id %s' % id}

    @h.jsonify
    def edit(self, id, format='html'):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}
