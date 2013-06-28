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

import logging
import os
import simplejson as json
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model import Morphology
from onlinelinguisticdatabase.model.meta import Session

log = logging.getLogger(__name__)

class TestMorphologybackupsController(TestController):

    def __init__(self, *args, **kwargs):
        TestController.__init__(self, *args, **kwargs)

    def tearDown(self):
        TestController.tearDown(self, dirs_to_destroy=['morphology'])

    @nottest
    def test_index(self):
        """Tests that ``GET /morphologybackups`` behaves correctly.
        """

        # Define some extra_environs
        view = {'test.authentication.role': u'viewer', 'test.application_settings': True}
        contrib = {'test.authentication.role': u'contributor', 'test.application_settings': True}
        admin = {'test.authentication.role': u'administrator', 'test.application_settings': True}

        # Create a corpus
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus',
            'description': u'A description of the corpus',
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        corpus_id = resp['id']

        # Create a morphology.
        params = self.morphology_create_params.copy()
        params.update({
            'name': u'Morphology',
            'description': u'A description of this morphology.',
            'script_type': u'lexc',
            'rules_corpus': corpus_id,
            'extract_morphemes_from_rules_corpus': True
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        morphology_count = Session.query(Morphology).count()
        morphology_dir = os.path.join(self.morphologies_path, 'morphology_%d' % resp['id'])
        morphology_dir_contents = os.listdir(morphology_dir)
        morphology_id = resp['id']
        assert morphology_count == 1
        assert resp['name'] == u'Morphology'
        assert resp['description'] == u'A description of this morphology.'
        assert 'morphology_%d.script' % morphology_id not in morphology_dir_contents # generate has not yet been requested.
        assert response.content_type == 'application/json'
        assert resp['script_type'] == u'lexc'
        assert resp['rules'] == u''
        assert resp['rules_generated'] == None
        assert resp['generate_attempt'] == None

        # Update the morphology as the admin to create a morphology backup.
        params = self.morphology_create_params.copy()
        params.update({
            'name': u'Morphology Renamed',
            'description': u'A description of this morphology.',
            'script_type': u'lexc',
            'rules_corpus': corpus_id,
            'extract_morphemes_from_rules_corpus': True
        })
        params = json.dumps(params)
        response = self.app.put(url('morphology', id=morphology_id), params,
                        self.json_headers, admin)
        resp = json.loads(response.body)
        morphology_count = Session.query(model.Morphology).count()
        assert response.content_type == 'application/json'
        assert morphology_count == 1

        # Now Update the morphology as the default contributor to create a second backup.
        params = self.morphology_create_params.copy()
        params.update({
            'name': u'Morphology Renamed by Contributor',
            'description': u'A description of this morphology.',
            'script_type': u'lexc',
            'rules_corpus': corpus_id,
            'extract_morphemes_from_rules_corpus': True
        })
        params = json.dumps(params)
        response = self.app.put(url('morphology', id=morphology_id), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        morphology_count = Session.query(model.Morphology).count()
        assert morphology_count == 1

        # Now GET the morphology backups (as the viewer).
        response = self.app.get(url('morphologybackups'), headers=self.json_headers,
                                extra_environ=view)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert response.content_type == 'application/json'

        # Now update the morphology.
        params = self.morphology_create_params.copy()
        params.update({
            'name': u'Morphology Updated',
            'description': u'A description of this morphology.',
            'script_type': u'lexc',
            'rules_corpus': corpus_id,
            'extract_morphemes_from_rules_corpus': True
        })
        params = json.dumps(params)
        response = self.app.put(url('morphology', id=morphology_id), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        morphology_count = Session.query(model.Morphology).count()
        assert morphology_count == 1

        # Now GET the morphology backups.  Admin and contrib should see 4 and the
        # viewer should see 1
        response = self.app.get(url('morphologybackups'), headers=self.json_headers,
                                extra_environ=contrib)
        resp = json.loads(response.body)
        all_morphology_backups = resp
        assert len(resp) == 3

        # Test the paginator GET params.
        paginator = {'items_per_page': 1, 'page': 2}
        response = self.app.get(url('morphologybackups'), paginator,
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['name'] == all_morphology_backups[1]['name']
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'MorphologyBackup', 'order_by_attribute': 'datetime_modified',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('morphologybackups'), order_by_params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        result_set = sorted(all_morphology_backups, key=lambda pb: pb['datetime_modified'], reverse=True)
        assert [pb['id'] for pb in resp] == [pb['id'] for pb in result_set]

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'MorphologyBackup', 'order_by_attribute': 'datetime_modified',
                     'order_by_direction': 'desc', 'items_per_page': 1, 'page': 3}
        response = self.app.get(url('morphologybackups'), params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert result_set[2]['name'] == resp['items'][0]['name']

        # Now test the show action:

        # Get a particular morphology backup
        response = self.app.get(url('morphologybackup', id=all_morphology_backups[0]['id']),
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert resp['name'] == all_morphology_backups[0]['name']
        assert response.content_type == 'application/json'

        # A nonexistent pb id will return a 404 error
        response = self.app.get(url('morphologybackup', id=100987),
                    headers=self.json_headers, extra_environ=view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no morphology backup with id 100987'
        assert response.content_type == 'application/json'

        # Attempting to call edit/new/create/delete/update on a read-only resource
        # will return a 404 response
        response = self.app.get(url('edit_morphologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.get(url('new_morphologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.post(url('morphologybackups'), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.put(url('morphologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.delete(url('morphologybackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'

