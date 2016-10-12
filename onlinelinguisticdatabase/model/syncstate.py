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

"""Sync State model."""

import logging
from sqlalchemy import Column, Sequence
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime
from onlinelinguisticdatabase.model.meta import Base, now, Session, uuid_unicode
import onlinelinguisticdatabase.model
from pylons import app_globals
import pprint
import time


log = logging.getLogger(__name__)


class SyncState(Base):
    """This model encodes the details of a synchronization state that holds
    between the current (assumedly client-side) OLD and another OLD living on a
    server.  It is treated like any other resource.
    """

    __tablename__ = 'syncstate'

    def __repr__(self):
        return '<SyncState (%s)>' % self.id

    id = Column(
        Integer, Sequence('tag_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36), default=uuid_unicode)

    # The URL of the server-side OLD that we are syncing with.
    master_url = Column(Unicode(1000))

    # Will indicate, via string, the sync state: 'syncing' vs. 'idle'
    state = Column(Unicode(100))

    # How often to perform a sync, in seconds.
    interval = Column(Integer, default=3)

    # Will hold JSON holding details about the last sync (attempt). For
    # example, what resources were synced, at what times, and what their last
    # modified timestamps looked like at the last sync.
    sync_details = Column(UnicodeText)

    # When the last sync occurred
    last_sync = Column(DateTime)

    datetime_entered = Column(DateTime)
    datetime_modified = Column(DateTime, default=now)

    def get_dict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'master_url': self.master_url,
            'state': self.state,
            'interval': self.interval,
            'sync_details': self.sync_details,  # TODO: json.loads
            'last_sync': self.last_sync,
            'datetime_modified': self.datetime_modified,
            'datetime_entered': self.datetime_entered
        }

    def sync(self):
        """Sync this OLD to the OLD at ``master_url``.
        Steps:

        1. Preflight: see if we can sync with the version of the OLD at
           master_url. Abort if not (how?)
        2. Get the signatures (ids and datemods) of our local resources, using
           ``get_models`` and ``get_resource_signature``.
        3. Get the signatures of the remote/master resources.
        4. Sync!

        """
        log.info('SyncState().sync() called against master {} on sync state'
                 ' model {}'.format(self.master_url, self.UUID))
        local_resources_state = self.get_local_resources_state()
        log.info(pprint.pformat(local_resources_state))

    def get_local_resources_state(self):
        local_resources_state = {}
        for model_name in self.resource_model_names:
            if model_name != 'Language':
                local_resources_state[model_name] = self.get_resource_signature(
                    model_name)
        return local_resources_state

    def get_resource_signature(self, model_name):
        """Return the signature for the resource corresponding to model
        ``model_name``. The signature is the UUID and datetime_modified of each
        model instance/resource in the database.

        """
        model = getattr(onlinelinguisticdatabase.model, model_name)
        return [(a, b, c.isoformat()) for a, b, c in
                Session.query(model).with_entities(
                    model.id,
                    model.UUID,
                    model.datetime_modified).all()]

    def start_sync(self, resource_model_names):
        """Initiate a scheduled sync between this OLD and the OLD at
        ``self.master_url`` such that the sync is performed every
        ``self.interval`` seconds.
        """
        log.info('APScheduler.add_job called against master {} on sync state'
                 ' model {} and interval {}'.format(self.master_url, self.UUID,
                 self.interval))
        self.resource_model_names = resource_model_names
        app_globals.scheduler.add_job(
            self.sync,
            'interval',
            seconds=self.interval,
            id=self.UUID
        )

    def stop_sync(self):
        """Stop the scheduled sync that is using this sync state."""
        log.info('APScheduler.remove_job called against master {} on sync state'
                 ' model {}'.format(self.master_url, self.UUID))
        app_globals.scheduler.remove_job(self.UUID)
