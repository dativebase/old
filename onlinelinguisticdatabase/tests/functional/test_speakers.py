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
from time import sleep
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Speaker

log = logging.getLogger(__name__)

################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestSpeakersController(TestController):

    @nottest
    def test_index(self):
        """Tests that GET /speakers returns an array of all speakers and that order_by and pagination parameters work correctly."""

        # Add 100 speakers.
        def create_speaker_from_index(index):
            speaker = model.Speaker()
            speaker.first_name = u'John%d' % index
            speaker.last_name = u'Doe%d' % index
            speaker.dialect = u'dialect %d' % index
            speaker.page_content = u'page content %d' % index
            return speaker
        speakers = [create_speaker_from_index(i) for i in range(1, 101)]
        Session.add_all(speakers)
        Session.commit()
        speakers = h.get_speakers(True)
        speakers_count = len(speakers)

        # Test that GET /speakers gives us all of the speakers.
        response = self.app.get(url('speakers'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == speakers_count
        assert resp[0]['first_name'] == u'John1'
        assert resp[0]['id'] == speakers[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'items_per_page': 23, 'page': 3}
        response = self.app.get(url('speakers'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['first_name'] == speakers[46].first_name

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'Speaker', 'order_by_attribute': 'first_name',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('speakers'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        result_set = sorted([s.first_name for s in speakers], reverse=True)
        assert result_set == [s['first_name'] for s in resp]

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'Speaker', 'order_by_attribute': 'first_name',
                     'order_by_direction': 'desc', 'items_per_page': 23, 'page': 3}
        response = self.app.get(url('speakers'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert result_set[46] == resp['items'][0]['first_name']

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'Speaker', 'order_by_attribute': 'first_name',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('speakers'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the order_by_model/Attribute
        # param is invalid.
        order_by_params = {'order_by_model': 'Speakerist', 'order_by_attribute': 'prenom',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('speakers'), order_by_params,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == speakers[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'items_per_page': u'a', 'page': u''}
        response = self.app.get(url('speakers'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'items_per_page': 0, 'page': -1}
        response = self.app.get(url('speakers'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /speakers creates a new speaker
        or returns an appropriate error if the input is invalid.
        """

        original_speaker_count = Session.query(Speaker).count()

        # Create a valid one
        params = self.speaker_create_params.copy()
        params.update({
            'first_name': u'John',
            'last_name': u'Doe',
            'page_content': u'page_content',
            'dialect': u'dialect'
        })
        params = json.dumps(params)
        response = self.app.post(url('speakers'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_speaker_count = Session.query(Speaker).count()
        assert new_speaker_count == original_speaker_count + 1
        assert resp['first_name'] == u'John'
        assert resp['dialect'] == u'dialect'
        assert response.content_type == 'application/json'

        # Invalid because first_name is too long
        params = self.speaker_create_params.copy()
        params.update({
            'first_name': u'John' * 400,
            'last_name': u'Doe',
            'page_content': u'page_content',
            'dialect': u'dialect'
        })
        params = json.dumps(params)
        response = self.app.post(url('speakers'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['first_name'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    @nottest
    def test_new(self):
        """Tests that GET /speakers/new returns an empty JSON object."""
        response = self.app.get(url('new_speaker'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /speakers/id updates the speaker with id=id."""

        # Create a speaker to update.
        params = self.speaker_create_params.copy()
        params.update({
            'first_name': u'first_name',
            'last_name': u'last_name',
            'page_content': u'page_content',
            'dialect': u'dialect'
        })
        params = json.dumps(params)
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speaker_count = Session.query(Speaker).count()
        speaker_id = resp['id']
        original_datetime_modified = resp['datetime_modified']

        # Update the speaker
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetime_modified for the update
        params = self.speaker_create_params.copy()
        params.update({
            'first_name': u'first_name',
            'last_name': u'last_name',
            'page_content': u'page_content',
            'dialect': u'updated dialect.'
        })
        params = json.dumps(params)
        response = self.app.put(url('speaker', id=speaker_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetime_modified = resp['datetime_modified']
        new_speaker_count = Session.query(Speaker).count()
        assert speaker_count == new_speaker_count
        assert datetime_modified != original_datetime_modified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        response = self.app.put(url('speaker', id=speaker_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        speaker_count = new_speaker_count
        new_speaker_count = Session.query(Speaker).count()
        our_speaker_datetime_modified = Session.query(Speaker).get(speaker_id).datetime_modified
        assert our_speaker_datetime_modified.isoformat() == datetime_modified
        assert speaker_count == new_speaker_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /speakers/id deletes the speaker with id=id."""

        # Create a speaker to delete.
        params = self.speaker_create_params.copy()
        params.update({
            'first_name': u'first_name',
            'last_name': u'last_name',
            'page_content': u'page_content',
            'dialect': u'dialect'
        })
        params = json.dumps(params)
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speaker_count = Session.query(Speaker).count()
        speaker_id = resp['id']

        # Now delete the speaker
        response = self.app.delete(url('speaker', id=speaker_id), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        new_speaker_count = Session.query(Speaker).count()
        assert new_speaker_count == speaker_count - 1
        assert resp['id'] == speaker_id
        assert response.content_type == 'application/json'

        # Trying to get the deleted speaker from the db should return None
        deleted_speaker = Session.query(Speaker).get(speaker_id)
        assert deleted_speaker == None
        assert response.content_type == 'application/json'

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('speaker', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no speaker with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('speaker', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    @nottest
    def test_show(self):
        """Tests that GET /speakers/id returns the speaker with id=id or an appropriate error."""

        # Create a speaker to show.
        params = self.speaker_create_params.copy()
        params.update({
            'first_name': u'first_name',
            'last_name': u'last_name',
            'page_content': u'page_content',
            'dialect': u'dialect'
        })
        params = json.dumps(params)
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speaker_id = resp['id']

        # Try to get a speaker using an invalid id
        id = 100000000000
        response = self.app.get(url('speaker', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no speaker with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('speaker', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('speaker', id=speaker_id), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['first_name'] == u'first_name'
        assert resp['dialect'] == u'dialect'
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /speakers/id/edit returns a JSON object of data necessary to edit the speaker with id=id.

        The JSON object is of the form {'speaker': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a speaker to edit.
        params = self.speaker_create_params.copy()
        params.update({
            'first_name': u'first_name',
            'last_name': u'last_name',
            'page_content': u'page_content',
            'dialect': u'dialect'
        })
        params = json.dumps(params)
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speaker_id = resp['id']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_speaker', id=speaker_id), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_speaker', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no speaker with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_speaker', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_speaker', id=speaker_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['speaker']['first_name'] == u'first_name'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'
