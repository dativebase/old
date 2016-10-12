"""This module should run tests on the sync functionality of the OLD, i.e., the
functionality that allows the present (client-side) OLD to sync with another
(server-side) OLD.

At present, this module is a script that uses requests to create sync state
models in the target (client-side) OLD.

"""

import pprint
from onlinelinguisticdatabase.lib.oldclient import OLDClient

CLIENT_URL = 'http://127.0.0.1:5001'
CLIENT_USERNAME = 'admin'
CLIENT_PASSWORD = 'adminA_1'

MASTER_URL = 'http://127.0.0.1:5000'
MASTER_USERNAME = 'admin'
MASTER_PASSWORD = 'adminA_1'


def get_all_sync_states(c):
    return c.get('syncstates')


def delete_sync_state(c, sync_state):
    c.delete('syncstates/{}'.format(sync_state['id']))


def delete_all_sync_states(c):
    for sync_state in get_all_sync_states(c):
        delete_sync_state(c, sync_state)


def create_new_sync_state(c):
    syncstate_object = c.syncstate_create_params.copy()
    syncstate_object['master_url'] = MASTER_URL
    #syncstate_object['master_url'] = CLIENT_URL
    return c.create('syncstates', syncstate_object)


if __name__ == '__main__':
    c = OLDClient(CLIENT_URL)
    c.login(CLIENT_USERNAME, CLIENT_PASSWORD)
    delete_all_sync_states(c)
    print(create_new_sync_state(c))
    pprint.pprint(get_all_sync_states(c))
