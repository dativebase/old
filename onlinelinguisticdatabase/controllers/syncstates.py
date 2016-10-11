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

"""Contains the :class:`SyncStatesController` and its auxiliary functions.

.. module:: syncstates
   :synopsis: Contains the sync states controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from uuid import uuid4
from pylons import request, response, config, url
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import SyncStateSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import SyncState

log = logging.getLogger(__name__)


class SyncstatesController(BaseController):
    """Generate responses to requests on sync state resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::

       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('SyncState', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all sync state resources.

        :URL: ``GET /syncstates`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all sync state resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for
           the query string parameters that effect ordering and pagination.

        """
        log.info('GET syncstates/ called')
        app_URL = url('/', qualified=True)
        log.info('We are at this URL: {}'.format(app_URL))
        try:
            query = Session.query(SyncState)
            query = h.add_order_by(
                query, dict(request.GET), self.query_builder)
            return h.add_pagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator'])
    def create(self):
        """Create a new sync state resource and return it.

        :URL: ``POST /syncstates``
        :request body: JSON object representing the sync state to create.
        :returns: the newly created sync state.

        """
        try:
            schema = SyncStateSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            sync_state = create_new_sync_state(data)
            Session.add(sync_state)
            Session.commit()
            return sync_state
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator'])
    def new(self):
        """Return the data necessary to create a new sync state.

        :URL: ``GET /syncstates/new``.
        :returns: an empty dictionary.

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator'])
    def update(self, id):
        """Update a sync state and return it.

        :URL: ``PUT /syncstates/id``
        :Request body: JSON object representing the sync state with updated
            attribute values.
        :param str id: the ``id`` value of the sync state to be updated.
        :returns: the updated sync state model.

        """
        sync_state = Session.query(SyncState).get(int(id))
        if sync_state:
            try:
                schema = SyncStateSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                sync_state = update_sync_state(sync_state, data)
                # sync_state will be False if there are no changes (cf.
                # update_sync_state).
                if sync_state:
                    Session.add(sync_state)
                    Session.commit()
                    return sync_state
                else:
                    response.status_int = 400
                    return {'error': (u'The update request failed because the'
                            ' submitted data were not new.')}
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no sync state with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator'])
    def delete(self, id):
        """Delete an existing sync state and return it.

        :URL: ``DELETE /syncstates/id``
        :param str id: the ``id`` value of the sync state to be deleted.
        :returns: the deleted sync state model.

        """
        sync_state = Session.query(SyncState).get(id)
        if sync_state:
            Session.delete(sync_state)
            Session.commit()
            return sync_state
        else:
            response.status_int = 404
            return {'error': 'There is no sync state with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a sync state.

        :URL: ``GET /syncstates/id``
        :param str id: the ``id`` value of the sync state to be returned.
        :returns: a sync state model object.

        """
        sync_state = Session.query(SyncState).get(id)
        if sync_state:
            return sync_state
        else:
            response.status_int = 404
            return {'error': 'There is no sync state with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator'])
    def edit(self, id):
        """Return a sync state resource and the data needed to update it.

        :URL: ``GET /syncstates/edit``
        :param str id: the ``id`` value of the sync state that will be updated.
        :returns: a dictionary of the form::

                {"sync_state": {...}, "data": {...}}

            where the value of the ``sync_state`` key is a dictionary
            representation of the sync state and the value of the ``data`` key
            is an empty dictionary.

        """
        sync_state = Session.query(SyncState).get(id)
        if sync_state:
            return {'data': {}, 'sync_state': sync_state}
        else:
            response.status_int = 404
            return {'error': 'There is no sync state with id %s' % id}


###############################################################################
# SyncState Create & Update Functions
###############################################################################

def create_new_sync_state(data):
    """Create a new sync state.

    :param dict data: the data for the sync state to be created.
    :returns: an SQLAlchemy model object representing the sync state.

    """
    sync_state = SyncState()

    # What the creator controls:
    sync_state.master_url = data['master_url']
    sync_state.state = data['state']
    sync_state.interval = data['interval']

    # What the system controls:
    sync_state.datetime_entered = sync_state.datetime_modified = \
        datetime.datetime.utcnow()
    sync_state.UUID = unicode(uuid4())

    # Begin syncing if state is set thus.
    if sync_state.state == 'syncing':
        sync_state.start_sync()

    # The OLD sync logic determines the values of these attributes, not the
    # client.
    # sync_state.sync_details
    # sync_state.last_sync

    return sync_state


def update_sync_state(sync_state, data):
    """Update a sync state.

    :param sync_state: the sync state model to be updated.
    :param dict data: representation of the updated sync state.
    :returns: the updated sync state model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = sync_state.set_attr(
        'master_url', h.normalize(data['master_url']), changed)
    changed = sync_state.set_attr(
        'interval', h.normalize(data['interval']), changed)

    # Stop or start syncing, if the state has been changed.
    original_state = sync_state.state
    changed = sync_state.set_attr(
        'state', h.normalize(data['state']), changed)
    if original_state == 'syncing' and sync_state.state != 'syncing':
        sync_state.stop_sync()
    if original_state != 'syncing' and sync_state.state == 'syncing':
        sync_state.start_sync()


    if changed:
        sync_state.datetime_modified = datetime.datetime.utcnow()
        return sync_state
    return changed
