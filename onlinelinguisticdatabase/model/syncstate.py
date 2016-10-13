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
import simplejson as json
from sqlalchemy import Column, Sequence
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime
from onlinelinguisticdatabase.model.meta import Base, now, Session, uuid_unicode
import onlinelinguisticdatabase.model
from onlinelinguisticdatabase.lib.oldclient import OLDClient
from pylons import app_globals
import pprint
import time


log = logging.getLogger(__name__)

# Models that we do not sync with the master (server-side) OLD.
NO_SYNC_MODELS = (
    'Language',
    'SyncState'
)


class SyncState(Base):
    """This model encodes the details of a synchronization state that holds
    between the current (assumedly client-side) OLD and another OLD living on a
    server. It is treated like any other resource.

    WARNING: there is a potential issue related to syncing and user
    authorization.  If the user is not an administrator or an unrestricted
    contributor, then they may not be able to access all resources. How do we
    deal with this?

    TODOs:

    1. Create a testing environment that sets up two OLDs and confirms correct
       syncing behaviour between the client and the master.
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

    # Holds a JSON object detailing the last sync (attempt). Currently planned
    # schema::
    #   {
    #       "<resource_name>": {
    #           "<UUID>": {
    #               "master_id": "<master.resource.id>",
    #               "client_id": "<client.resource.id>",
    #               "sync": {
    #                   "master_datetime_modified": "<master.resource.datetime_modified>"
    #                   "client_datetime_modified": "<client.resource.datetime_modified>"
    #               }
    #           }
    #       }
    #   }
    sync_details = Column(UnicodeText, default=u'{}')

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

    #==========================================================================
    # Sync Logic
    #==========================================================================

    def start_sync(self):
        """Initiate a scheduled sync between this OLD and the OLD at
        ``self.master_url`` such that the sync is performed every
        ``self.interval`` seconds.
        """
        log.info('APScheduler.add_job called against master {} on sync state'
                 ' model {} and interval {}'.format(self.master_url, self.UUID,
                 self.interval))
        self.resource_model_names = app_globals.resource_model_names
        self.version = app_globals.version
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

    def sync(self):
        """Sync this OLD to the OLD at ``master_url``. This is the scheduled
        method, i.e., the one that is called in a separate thread at regular
        intervals.

        Steps:

        1. Preflight: see if we can login to the master OLD and determine
           whether our versions are compatible for syncing.
        2. Get the signatures (ids and datemods) of our local resources.
        3. Get the signatures of the remote/master resources.
        4. Sync!

        TODO/NOTE: the datetime_modified values of the client and the master
        will NEVER be identical. Really we need to compare the current state of
        the master to the state of the master when we last synced with it, and
        probably also to the current state of the client.

        UUIDs are constant. So we create a JSON object that maps resource UUIDs
        to objects that encode the last sync, if any. This information is held
        in ``self.sync_details``::

            {
                "<resource_name>": {
                    "<UUID>": {
                        "master_id": "<master.resource.id>",
                        "client_id": "<client.resource.id>",
                        "sync": {
                            "master_datetime_modified": "<master.resource.datetime_modified>"
                            "client_datetime_modified": "<client.resource.datetime_modified>"
                        }
                    }
                }
            }
        """
        log.info('Attempting to sync with master OLD at {} using sync state'
                 ' model {}'.format(self.master_url, self.UUID))
        response = self.handshake()
        if response is False:
            log.warning('Unable to sync with master OLD at'
                        ' {}'.format(self.master_url))
            return
        local_resources_state = self.get_local_resources_state()

        log.info('CLIENT RESOURCE STATE')
        log.info(pprint.pformat(local_resources_state))

        # TODO: in a single response, the master should be able to respond with
        # its entire resource state (with HTTP caching). Use info.py controller.
        master_resources_state = self.get_master_resources_state()

        log.info('MASTER RESOURCE STATE')
        log.info(pprint.pformat(master_resources_state))

        sync_details = json.loads(self.sync_details)
        """
        Syncing Algorithm:

        1. Resource X is on master but not client.
           Q: Has client synced X before (cf. sync_details)?
           a. Yes. :. X has been deleted locally.
              Q: Has X been changed on master since last sync (compare
              sync_details to master state)?
              i. Yes. :. CONFLICT.
                 Q: Is remote modifier of X same as current user?
                 I. Yes. :. Destroy X on master
                 II. No. :. **Require user intervention?**
              ii. No. :. Destroy X on master.
           b. No. :. X was created remotely. Create X locally.

        2. Resource X is on client but not master.
           Q: Has client synced X before?
           a. Yes. :. X has been destroyed remotely.
              Q: Is remote destroyer same as current user?
              i. Yes. :. Destroy X on client.
              ii. No. **Require user intervention?**
                  Choices:
                  - destroy X on client.
                  - destroy X on client and then recreate copy of it on client
                    and master
           b. No. :. Create X on master

        3. Resource X is on client and on master.
           - If X has changed on client AND master since last sync, ...
             - If most recent change is on client, update master X to match
               client X.
             - If most recent change is on master, update client X to match
               master X.
           - ElIf X has changed on client AND NOT on master since last sync, ...
             - Update master X to match client X.
           - ElIf X has changed on master AND NOT on client since last sync, ...
             - Update client X to match master X.
           - Else
             - Do nothing.
        """
        for mr_name, mr_state in master_resources_state.iteritems():
            lr_state = local_resources_state[mr_name]
            in_master_not_client = [uuid for uuid in mr_state if uuid not in
                                    lr_state]
            if in_master_not_client:
                log.info('The following {} resources are in master but not'
                         ' client: {}'.format(mr_name,
                             ' '.join(in_master_not_client)))
            in_client_not_master = [uuid for uuid in lr_state if uuid not in
                                    mr_state]
            if in_client_not_master:
                log.info('The following {} resources are in client but not'
                         ' master: {}'.format(mr_name,
                             ' '.join(in_client_not_master)))

    def handshake(self):
        """Ping the master OLD and get its version number. Return ``True`` if
        we can sync with an OLD of that version, ``False`` otherwise. Present
        strategy is (following semver) to return ``True`` so long as the MAJOR
        version numbers are identical.
        """
        log.info('Attempting to login to the master OLD at {}'.format(
                 self.master_url))
        self.old_client = OLDClient(self.master_url)
        # TODO: how to get/store these securely and conveniently?
        MASTER_USERNAME = 'admin'
        MASTER_PASSWORD = 'adminA_1'
        authenticated = self.old_client.login(MASTER_USERNAME, MASTER_PASSWORD)
        if not authenticated:
            log.info('Failed to login to the master OLD at {}'.format(
                     self.master_url))
            return False
        our_version = self.version
        ping = self.old_client.get('')
        try:
            master_version = ping['version']
        except Exception:
            log.warning('Failed to retrieve a version number from the master'
                        ' OLD at {}'.format(self.master_url))
            return False
        else:
            our_major_version = our_version.split('.')[0]
            master_major_version = master_version.split('.')[0]
            if our_major_version == master_major_version:
                log.info('Client OLD at version {} can sync with master OLD {}'
                         ' at version {}'.format(our_version, self.master_url,
                              master_version))
                return True
            else:
                log.warning('Client OLD at version {} can not sync with master'
                            ' OLD {} at version {}'.format(our_version,
                                self.master_url, master_version))
                return False
        return False

    def get_local_resources_state(self):
        """Return a dict representing the state of our resources. For each
        resource model key, the value is an array of 3-tuples: id, UUID and
        datetime_modified.
        """
        local_resources_state = {}
        for model_name in self.resource_model_names:
            if model_name not in NO_SYNC_MODELS:
                local_resources_state[model_name] = self.get_resource_signature(
                    model_name)
        return local_resources_state

    def get_resource_signature(self, model_name):
        """Return the signature for the resource corresponding to model
        ``model_name``. The signature is the id, UUID and datetime_modified of
        each model instance/resource in the database.
        """
        model = getattr(onlinelinguisticdatabase.model, model_name)
        return dict([(uuid, (id_, dm.isoformat())) for id_, uuid, dm in
                Session.query(model).with_entities(
                    model.id,
                    model.UUID,
                    model.datetime_modified).all()])

    def get_master_resources_state(self):
        """Get the state of the resources on the master OLD that we want to
        sync with. Do this via HTTP calls to the REST API.
        """
        master_resources_state = {}
        for model_name, resource_name in self.resource_model_names.items():
            if model_name not in NO_SYNC_MODELS:
                master_resources_state[model_name] = \
                    self.request_resource_signature(resource_name)
        return master_resources_state

    # We have to use a paginator because of how the OLD's REST API currently
    # works. Here we set items per page to 1M to (hopefully) get all.
    # WARNING: just a hack until we fix the API or do recursive paginated
    # requests.
    paginator = {
        'page': 1,
        'items_per_page': 1000000,
        'minimal': 1
    }

    def request_resource_signature(self, resource_name):
        """Make requests agains the master OLD to each of its resources so we
        know what state they are in. TODO: it might be beneficial to use
        pagination in case there are really large resource sets...

        This is what a paginated request to a resource with the minimal flag
        returns::

            {
                u'paginator': {
                    u'count': 2,
                    u'items_per_page': 1000,
                    u'page': 1,
                    u'minimal': u'1'
                },
                u'items': [
                    {
                        u'id': 1,
                        u'datetime_modified': u'2016-10-12T16:01:25.991559',
                        u'UUID': u'993a9834-2143-45a4-bf95-55e2a4f39546'
                    },
                    {
                        u'id': 2,
                        u'datetime_modified': u'2016-10-12T16:01:25.991929',
                        u'UUID': u'9e4dc785-6e0c-4a52-b893-46076d2a0d3d'
                    }
                ]
            }

        NOTE: the applicationsettings resource is unusual: it always returns an
        array of all application settings resources, and completely ignores
        pagination and minimal GET params.
        """
        if resource_name == 'applicationsettings':
            return dict([(r['UUID'], (r['id'], r['datetime_modified'])) for r in
                         self.old_client.get(resource_name,
                         params=self.paginator)])
        else:
            return dict([(r['UUID'], (r['id'], r['datetime_modified'])) for r in
                         self.old_client.get(resource_name,
                         params=self.paginator).get('items', [])])

