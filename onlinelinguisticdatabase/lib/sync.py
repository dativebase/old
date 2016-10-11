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

"""Sync: Synchronize this OLD, which is presumably running on a user's
computer, with a server-side OLD.

Development Notes
===============================================================================

Install Advanced Python Scheduler::

    $ pip install apscheduler

It looks like I will want to use an APScheduler ``BackgroundScheduler``, which
is used when you want the scheduler to run in the background inside your
application.

I will use the 'interval' trigger type.


TODOs
===============================================================================

1. Add apscheduler to install requirements

"""

from datetime import datetime
from pylons import app_globals
import os
import sys
import time


def sync(sync_state_model):
    """Sync this OLD to the OLD at ``master_url``."""
    print 'I want to sync to the master OLD {}'.format(
        sync_state_model.master_url)


def schedule_sync(sync_state_model):
    """Initiate a scheduled sync between this OLD and the OLD at ``master_url``
    such that the sync is performed every ``interval`` seconds.
    """

    app_globals.scheduler.add_job(
        sync,
        'interval',
        [sync_state_model],  # args to ``sync``
        seconds=sync_state_model.interval,
        id=sync_state_model.UUID
    )

if __name__ == '__main__':
    print 'hi'
