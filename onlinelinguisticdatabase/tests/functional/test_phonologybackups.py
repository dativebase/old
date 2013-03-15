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

import datetime
import logging
import os
import webtest
import codecs
import simplejson as json
from nose.tools import nottest
from base64 import encodestring
from paste.deploy import appconfig
from sqlalchemy.sql import desc
from uuid import uuid4
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model import Phonology
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder

log = logging.getLogger(__name__)


class TestPhonologybackupsController(TestController):

    createParams = {
        'name': u'',
        'description': u'',
        'script': u''
    }

    here = appconfig('config:test.ini', relative_to='.')['here']
    researchersPath = os.path.join(here, 'files', 'researchers')
    phonologyPath = os.path.join(here, 'analysis', 'phonology')
    testPhonologyScriptPath = os.path.join(here, 'onlinelinguisticdatabase',
                                    'tests', 'data', 'test_phonology.script')
    testPhonologyScript = h.normalize(
        codecs.open(testPhonologyScriptPath, 'r', 'utf8').read())

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    def tearDown(self):
        # Clear all models in the database except Language; recreate the users.
        h.clearAllModels()
        h.destroyAllPhonologyDirectories()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that ``GET /phonologybackups`` behaves correctly.
        """

        # Get the users
        users = h.getUsers()
        contributorId = [u for u in users if u.role==u'contributor'][0].id
        administratorId = [u for u in users if u.role==u'administrator'][0].id

        # Define some extra_environs
        view = {'test.authentication.role': u'viewer', 'test.applicationSettings': True}
        contrib = {'test.authentication.role': u'contributor', 'test.applicationSettings': True}
        admin = {'test.authentication.role': u'administrator', 'test.applicationSettings': True}

        # Create a phonology.
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyId = resp['id']
        phonologyUUID = resp['UUID']
        assert phonologyCount == 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert 'phonology_%d.script' % phonologyId in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testPhonologyScript

        # Update the phonology as the admin to create a phonology backup.
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology Renamed',
            'description': u'Covers a lot of the data.',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonologyId), params,
                        self.json_headers, admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(model.Phonology).count()
        assert response.content_type == 'application/json'
        assert phonologyCount == 1

        # Now Update the phonology as the default contributor to create a second backup.
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology Renamed by Contributor',
            'description': u'Covers a lot of the data.',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonologyId), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        phonologyCount = Session.query(model.Phonology).count()
        assert phonologyCount == 1

        # Now GET the phonology backups (as the viewer).
        response = self.app.get(url('phonologybackups'), headers=self.json_headers,
                                extra_environ=view)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert response.content_type == 'application/json'

        # Now update the phonology.
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology Updated',
            'description': u'Covers a lot of the data.',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonologyId), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        phonologyCount = Session.query(model.Phonology).count()
        assert phonologyCount == 1

        # Now GET the phonology backups.  Admin and contrib should see 4 and the
        # viewer should see 1
        response = self.app.get(url('phonologybackups'), headers=self.json_headers,
                                extra_environ=contrib)
        resp = json.loads(response.body)
        allPhonologyBackups = resp
        assert len(resp) == 3

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 1, 'page': 2}
        response = self.app.get(url('phonologybackups'), paginator,
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['name'] == allPhonologyBackups[1]['name']
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'PhonologyBackup', 'orderByAttribute': 'datetimeModified',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('phonologybackups'), orderByParams,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        resultSet = sorted(allPhonologyBackups, key=lambda pb: pb['datetimeModified'], reverse=True)
        assert [pb['id'] for pb in resp] == [pb['id'] for pb in resultSet]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'PhonologyBackup', 'orderByAttribute': 'datetimeModified',
                     'orderByDirection': 'desc', 'itemsPerPage': 1, 'page': 3}
        response = self.app.get(url('phonologybackups'), params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert resultSet[2]['name'] == resp['items'][0]['name']

        # Now test the show action:

        # Get a particular phonology backup
        response = self.app.get(url('phonologybackup', id=allPhonologyBackups[0]['id']),
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert resp['name'] == allPhonologyBackups[0]['name']
        assert response.content_type == 'application/json'

        # A nonexistent pb id will return a 404 error
        response = self.app.get(url('phonologybackup', id=100987),
                    headers=self.json_headers, extra_environ=view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no phonology backup with id 100987'
        assert response.content_type == 'application/json'

        # Attempting to call edit/new/create/delete/update on a read-only resource
        # will return a 404 response
        response = self.app.get(url('edit_phonologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.get(url('new_phonologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.post(url('phonologybackups'), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.put(url('phonologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.delete(url('phonologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'
