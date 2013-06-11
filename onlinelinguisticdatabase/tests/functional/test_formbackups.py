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
import simplejson as json
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder

log = logging.getLogger(__name__)


class TestFormbackupsController(TestController):

    @nottest
    def test_index(self):
        """Tests that GET & SEARCH /formbackups behave correctly.
        """

        # Add some test data to the database.
        application_settings = h.generate_default_application_settings()
        source = h.generate_default_source()
        restricted_tag = h.generate_restricted_tag()
        file1 = h.generate_default_file()
        file1.name = u'file1'
        file2 = h.generate_default_file()
        file2.name = u'file2'
        speaker = h.generate_default_speaker()
        Session.add_all([application_settings, source, restricted_tag, file1,
                         file2, speaker])
        Session.commit()
        speaker_id = speaker.id
        restricted_tag_id = restricted_tag.id
        tag_ids = [restricted_tag_id]
        file1_id = file1.id
        file2_id = file2.id
        file_ids = [file1_id, file2_id]

        # Create a restricted form (via request) as the default contributor
        users = h.get_users()
        administrator_id = [u for u in users if u.role==u'administrator'][0].id

        # Define some extra_environs
        view = {'test.authentication.role': u'viewer', 'test.application_settings': True}
        contrib = {'test.authentication.role': u'contributor', 'test.application_settings': True}
        admin = {'test.authentication.role': u'administrator', 'test.application_settings': True}

        params = self.form_create_params.copy()
        params.update({
            'transcription': u'Created by the Contributor',
            'translations': [{'transcription': u'test', 'grammaticality': u''}],
            'tags': [restricted_tag_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, contrib)
        form_count = Session.query(model.Form).count()
        resp = json.loads(response.body)
        form_id = resp['id']
        assert form_count == 1

        # Update our form (via request) as the default administrator; this
        # will create one form backup.
        params = self.form_create_params.copy()
        params.update({
            'translations': [{'transcription': u'test', 'grammaticality': u''}],
            'transcription': u'Updated by the Administrator',
            'speaker': speaker_id,
            'tags': tag_ids + [None, u''], # None and u'' ('') will be ignored by forms.update_form
            'enterer': administrator_id  # This should change nothing.
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=form_id), params,
                        self.json_headers, admin)
        resp = json.loads(response.body)
        form_count = Session.query(model.Form).count()
        assert form_count == 1

        # Finally, update our form (via request) as the default contributor.
        # Now we will have two form backups.
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'Updated by the Contributor',
            'translations': [{'transcription': u'test', 'grammaticality': u''}],
            'speaker': speaker_id,
            'tags': tag_ids,
            'files': file_ids
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=form_id), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        form_count = Session.query(model.Form).count()
        assert form_count == 1

        # Now GET the form backups as the restricted enterer of the original
        # form and expect to get them all.
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=contrib)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert response.content_type == 'application/json'

        # The admin should get them all too.
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # The viewer should get none because they're all restricted.
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        assert len(resp) == 0

        # Now update the form and de-restrict it.
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'Updated and de-restricted by the Contributor',
            'translations': [{'transcription': u'test', 'grammaticality': u''}],
            'speaker': speaker_id,
            'tags': [],
            'files': file_ids
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=form_id), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        form_count = Session.query(model.Form).count()
        assert form_count == 1

        # Now GET the form backups.  Admin and contrib should see 3 but the
        # viewer should still see none.
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=contrib)
        resp = json.loads(response.body)
        assert len(resp) == 3
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp) == 3
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        assert len(resp) == 0

        # Finally, update our form in some trivial way.
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'Updated by the Contributor *again*',
            'translations': [{'transcription': u'test', 'grammaticality': u''}],
            'speaker': speaker_id,
            'tags': [],
            'files': file_ids
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=form_id), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        form_count = Session.query(model.Form).count()
        assert form_count == 1

        # Now GET the form backups.  Admin and contrib should see 4 and the
        # viewer should see 1
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=contrib)
        resp = json.loads(response.body)
        assert len(resp) == 4
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        all_form_backups = resp
        assert len(resp) == 4
        response = self.app.get(url('formbackups'), headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        unrestricted_form_backup = resp[0]
        assert len(resp) == 1
        assert resp[0]['transcription'] == u'Updated and de-restricted by the Contributor'
        restricted_form_backups = [cb for cb in all_form_backups
                                       if cb != unrestricted_form_backup]
        assert len(restricted_form_backups) == 3

        # Test the paginator GET params.
        paginator = {'items_per_page': 1, 'page': 2}
        response = self.app.get(url('formbackups'), paginator, headers=self.json_headers,
                                extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['transcription'] == all_form_backups[1]['transcription']
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'FormBackup', 'order_by_attribute': 'datetime_modified',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('formbackups'), order_by_params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        result_set = sorted(all_form_backups, key=lambda cb: cb['datetime_modified'], reverse=True)
        assert [cb['id'] for cb in resp] == [cb['id'] for cb in result_set]

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'FormBackup', 'order_by_attribute': 'datetime_modified',
                     'order_by_direction': 'desc', 'items_per_page': 1, 'page': 3}
        response = self.app.get(url('formbackups'), params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert result_set[2]['transcription'] == resp['items'][0]['transcription']

        # Now test the show action:

        # Admin should be able to GET a particular restricted form backup
        response = self.app.get(url('formbackup', id=restricted_form_backups[0]['id']),
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert resp['transcription'] == restricted_form_backups[0]['transcription']
        assert response.content_type == 'application/json'

        # Viewer should receive a 403 error when attempting to do so.
        response = self.app.get(url('formbackup', id=restricted_form_backups[0]['id']),
                                headers=self.json_headers, extra_environ=view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Viewer should be able to GET the unrestricted form backup
        response = self.app.get(url('formbackup', id=unrestricted_form_backup['id']),
                                headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        assert resp['transcription'] == unrestricted_form_backup['transcription']

        # A nonexistent cb id will return a 404 error
        response = self.app.get(url('formbackup', id=100987),
                    headers=self.json_headers, extra_environ=view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no form backup with id 100987'
        assert response.content_type == 'application/json'

        # Test the search action
        self._add_SEARCH_to_web_test_valid_methods()

        # A search on form backup transcriptions using POST /formbackups/search
        json_query = json.dumps({'query': {'filter':
                        ['FormBackup', 'transcription', 'like', u'%Contributor%']}})
        response = self.app.post(url('/formbackups/search'), json_query,
                        self.json_headers, admin)
        resp = json.loads(response.body)
        result_set = [cb for cb in all_form_backups if u'Contributor' in cb['transcription']]
        assert len(resp) == len(result_set) == 3
        assert set([cb['id'] for cb in resp]) == set([cb['id'] for cb in result_set])
        assert response.content_type == 'application/json'

        # A search on form backup transcriptions using SEARCH /formbackups
        json_query = json.dumps({'query': {'filter':
                        ['FormBackup', 'transcription', 'like', u'%Administrator%']}})
        response = self.app.request(url('formbackups'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=admin)
        resp = json.loads(response.body)
        result_set = [cb for cb in all_form_backups if u'Administrator' in cb['transcription']]
        assert len(resp) == len(result_set) == 1
        assert set([cb['id'] for cb in resp]) == set([cb['id'] for cb in result_set])

        # Perform the two previous searches as a restricted viewer to show that
        # the restricted tag is working correctly.
        json_query = json.dumps({'query': {'filter':
                        ['FormBackup', 'transcription', 'like', u'%Contributor%']}})
        response = self.app.post(url('/formbackups/search'), json_query,
                        self.json_headers, view)
        resp = json.loads(response.body)
        result_set = [cb for cb in [unrestricted_form_backup]
                     if u'Contributor' in cb['transcription']]
        assert len(resp) == len(result_set) == 1
        assert set([cb['id'] for cb in resp]) == set([cb['id'] for cb in result_set])
        assert response.content_type == 'application/json'

        json_query = json.dumps({'query': {'filter':
                        ['FormBackup', 'transcription', 'like', u'%Administrator%']}})
        response = self.app.request(url('formbackups'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=view)
        resp = json.loads(response.body)
        result_set = [cb for cb in [unrestricted_form_backup]
                     if u'Administrator' in cb['transcription']]
        assert len(resp) == len(result_set) == 0

        # I'm just going to assume that the order by and pagination functions are
        # working correctly since the implementation is essentially equivalent
        # to that in the index action already tested above.

        # Attempting to call edit/new/create/delete/update on a read-only resource
        # will return a 404 response
        response = self.app.get(url('edit_formbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.get(url('new_formbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.post(url('formbackups'), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.put(url('formbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.delete(url('formbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'

    @nottest
    def test_new_search(self):
        """Tests that GET /formbackups/new_search returns the search parameters for searching the form backups resource."""
        query_builder = SQLAQueryBuilder('FormBackup')
        response = self.app.get(url('/formbackups/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['search_parameters'] == h.get_search_parameters(query_builder)
