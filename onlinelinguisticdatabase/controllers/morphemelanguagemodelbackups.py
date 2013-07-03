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

"""Contains the :class:`MorphemelanguagemodelbackupsController`.

.. module:: morphemelanguagemodelbackups
   :synopsis: Contains the morpheme language model backups controller.

"""

import logging
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import MorphemeLanguageModelBackup

log = logging.getLogger(__name__)

class MorphemelanguagemodelbackupsController(BaseController):
    """Generate responses to requests on morpheme language model backup resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::

       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    .. note::

        Morpheme language model backups are created when updating and deleting
        morpheme language models; they cannot be created directly and they should
        never be deleted.  This controller facilitates retrieval of morpheme 
        language model backups only.

    """

    query_builder = SQLAQueryBuilder('MorphemeLanguageModelBackup', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all morpheme language model backup resources.

        :URL: ``GET /morphemelanguagemodelbackups`` 
        :returns: a list of all morpheme language model backup resources.

        """
        try:
            query = Session.query(MorphemeLanguageModelBackup)
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
        """Return a morpheme language model backup.

        :URL: ``GET /morphemelanguagemodelbackups/id``
        :param str id: the ``id`` value of the morpheme language model backup to be returned.
        :returns: a morpheme language model backup model object.

        """
        morpheme_language_model_backup = Session.query(MorphemeLanguageModelBackup).get(id)
        if morpheme_language_model_backup:
            return morpheme_language_model_backup
        else:
            response.status_int = 404
            return {'error': 'There is no morpheme language model backup with id %s' % id}

    @h.jsonify
    def edit(self, id, format='html'):
        response.status_int = 404
        return {'error': 'This resource is read-only.'}
