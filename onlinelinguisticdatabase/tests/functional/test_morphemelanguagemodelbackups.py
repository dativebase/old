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
from onlinelinguisticdatabase.model import MorphemeLanguageModel
from onlinelinguisticdatabase.model.meta import Session

log = logging.getLogger(__name__)

class TestMorphemelanguagemodelbackupsController(TestController):

    def __init__(self, *args, **kwargs):
        TestController.__init__(self, *args, **kwargs)

    def tearDown(self):
        TestController.tearDown(self, dirs_to_destroy=['morpheme_language_model'])

    @nottest
    def test_index(self):
        """Tests that ``GET /morphemelanguagemodelbackups`` behaves correctly.
        """

        # Define some extra_environs
        view = {'test.authentication.role': u'viewer', 'test.application_settings': True}
        contrib = {'test.authentication.role': u'contributor', 'test.application_settings': True}
        admin = {'test.authentication.role': u'administrator', 'test.application_settings': True}

        # Create a form search that finds all forms (there are none)
        query = {'filter': ['Form', 'transcription', 'like', u'%_%']}
        params = self.form_search_create_params.copy()
        params.update({
            'name': u'Find anything',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        form_search_id = json.loads(response.body)['id']

        # Create a corpus based on the form search just created
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of sentences',
            'form_search': form_search_id
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        corpus_id = json.loads(response.body)['id']

        # Create a morpheme language model using the corpus just created.
        name = u'Morpheme language model'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'corpus': corpus_id,
            'toolkit': 'mitlm'
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'
        assert resp['order'] == 3
        assert resp['smoothing'] == u'' # The ModKN smoothing algorithm is the implicit default with MITLM
        assert resp['restricted'] == False

        # Update the morpheme language model as the admin to create a backup.
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': u'Morpheme language model renamed',
            'corpus': corpus_id,
            'toolkit': u'mitlm'
        })
        params = json.dumps(params)
        response = self.app.put(url('morphemelanguagemodel', id=morpheme_language_model_id), params,
                        self.json_headers, admin)
        resp = json.loads(response.body)
        morpheme_language_model_count = Session.query(model.MorphemeLanguageModel).count()
        assert response.content_type == 'application/json'
        assert morpheme_language_model_count == 1

        # Now Update the morpheme language model as the default contributor to create a second backup.
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': u'Morpheme language model renamed by contributor',
            'corpus': corpus_id,
            'toolkit': u'mitlm'
        })
        params = json.dumps(params)
        response = self.app.put(url('morphemelanguagemodel', id=morpheme_language_model_id), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        morpheme_language_model_count = Session.query(MorphemeLanguageModel).count()
        assert morpheme_language_model_count == 1

        # Now GET the morpheme language model backups (as the viewer).
        response = self.app.get(url('morphemelanguagemodelbackups'), headers=self.json_headers,
                                extra_environ=view)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert response.content_type == 'application/json'

        # Now update the morpheme language model yet again.
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': u'Morpheme language model updated yet again',
            'corpus': corpus_id,
            'toolkit': u'mitlm'
        })
        params = json.dumps(params)
        response = self.app.put(url('morphemelanguagemodel', id=morpheme_language_model_id), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        morpheme_language_model_count = Session.query(model.MorphemeLanguageModel).count()
        assert morpheme_language_model_count == 1

        # Now GET the morpheme language model backups.
        response = self.app.get(url('morphemelanguagemodelbackups'), headers=self.json_headers,
                                extra_environ=contrib)
        resp = json.loads(response.body)
        all_morpheme_language_model_backups = resp
        assert len(resp) == 3

        # Test the paginator GET params.
        paginator = {'items_per_page': 1, 'page': 2}
        response = self.app.get(url('morphemelanguagemodelbackups'), paginator,
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['name'] == all_morpheme_language_model_backups[1]['name']
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'MorphemeLanguageModelBackup', 'order_by_attribute': 'datetime_modified',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('morphemelanguagemodelbackups'), order_by_params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        result_set = sorted(all_morpheme_language_model_backups, key=lambda pb: pb['datetime_modified'], reverse=True)
        assert [pb['id'] for pb in resp] == [pb['id'] for pb in result_set]

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'MorphemeLanguageModelBackup', 'order_by_attribute': 'datetime_modified',
                     'order_by_direction': 'desc', 'items_per_page': 1, 'page': 3}
        response = self.app.get(url('morphemelanguagemodelbackups'), params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert result_set[2]['name'] == resp['items'][0]['name']

        # Now test the show action:

        # Get a particular morpheme language model backup
        response = self.app.get(url('morphemelanguagemodelbackup', id=all_morpheme_language_model_backups[0]['id']),
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert resp['name'] == all_morpheme_language_model_backups[0]['name']
        assert response.content_type == 'application/json'

        # A nonexistent morpheme language model backup id will return a 404 error
        response = self.app.get(url('morphemelanguagemodelbackup', id=100987),
                    headers=self.json_headers, extra_environ=view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no morpheme language model backup with id 100987'
        assert response.content_type == 'application/json'

        # Attempting to call edit/new/create/delete/update on a read-only resource
        # will return a 404 response
        response = self.app.get(url('edit_morphemelanguagemodelbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.get(url('new_morphemelanguagemodelbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.post(url('morphemelanguagemodelbackups'), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.put(url('morphemelanguagemodelbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.delete(url('morphemelanguagemodelbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'

