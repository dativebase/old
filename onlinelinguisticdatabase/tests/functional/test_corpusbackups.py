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
import simplejson as json
from time import sleep
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Corpus, CorpusBackup
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder

log = logging.getLogger(__name__)

class TestCorpusbackupsController(TestController):

    def __init__(self, *args, **kwargs):
        TestController.__init__(self, *args, **kwargs)
        self._add_SEARCH_to_web_test_valid_methods()

    def tearDown(self):
        TestController.tearDown(self, dirs_to_destroy=['corpus'])

    @nottest
    def test_index(self):
        """Tests that GET & SEARCH /corpusbackups behave correctly.
        """

        tag = model.Tag()
        tag.name = u'random tag name'
        Session.add(tag)
        Session.commit()
        tag_id = tag.id

        # Add 10 forms and use them to generate a valid value for ``test_corpus_content``
        def create_form_from_index(index):
            form = model.Form()
            form.transcription = u'Form %d' % index
            translation = model.Translation()
            translation.transcription = u'Translation %d' % index
            form.translation = translation
            return form
        forms = [create_form_from_index(i) for i in range(1, 10)]
        Session.add_all(forms)
        Session.commit()
        forms = h.get_forms()
        half_forms = forms[:5]
        form_ids = [form.id for form in forms]
        half_form_ids = [form.id for form in half_forms]
        test_corpus_content = u','.join(map(str, form_ids))
        test_corpus_half_content = u','.join(map(str, half_form_ids))

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-zA-Z]{3,}']}
        params = json.dumps({
            'name': u'form search',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        response = self.app.post(url('formsearches'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        form_search_id = resp['id']

        # Generate some valid corpus creation input parameters.
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': test_corpus_content
        })
        params = json.dumps(params)

        # Attempt to create a corpus as a viewer and expect to fail
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Successfully create a corpus as the admin
        assert os.listdir(self.corpora_path) == []
        original_corpus_count = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpus_id = resp['id']
        new_corpus_count = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpus_id)
        corpus_form_ids = sorted([f.id for f in corpus.forms])
        corpus_dir = os.path.join(self.corpora_path, 'corpus_%d' % corpus_id)
        corpus_dir_contents = os.listdir(corpus_dir)
        assert new_corpus_count == original_corpus_count + 1
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpus_dir_contents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == test_corpus_content
        assert corpus_form_ids == sorted(form_ids)

        # Update the corpus as the contributor -- now we should have one backup
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a little less data.',
            'content': test_corpus_half_content
        })
        params = json.dumps(params)
        response = self.app.put(url('corpus', id=corpus_id), params,
                self.json_headers, self.extra_environ_contrib)
        resp = json.loads(response.body)
        corpus_count = new_corpus_count
        new_corpus_count = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpus_id)
        corpus_form_ids = sorted([f.id for f in corpus.forms])
        assert new_corpus_count == corpus_count
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a little less data.' 
        assert response.content_type == 'application/json'
        assert resp['content'] == test_corpus_half_content
        assert corpus_form_ids == sorted(half_form_ids)

        # Update the corpus again -- now we should have two backups
        sleep(1)
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a little less data.',
            'content': test_corpus_half_content,
            'tags': [tag_id]
        })
        params = json.dumps(params)
        response = self.app.put(url('corpus', id=corpus_id), params,
                self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        corpus_count = new_corpus_count
        new_corpus_count = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpus_id)
        corpus_form_ids = sorted([f.id for f in corpus.forms])
        assert new_corpus_count == corpus_count
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a little less data.' 
        assert response.content_type == 'application/json'
        assert resp['content'] == test_corpus_half_content
        assert corpus_form_ids == sorted(half_form_ids)

        all_corpus_backups = Session.query(CorpusBackup).order_by(CorpusBackup.id).all()
        all_corpus_backup_ids = [cb.id for cb in all_corpus_backups]
        all_corpus_backup_descriptions = [cb.description for cb in all_corpus_backups]

        # Now request the corpus backups as either the contributor or the viewer and 
        # expect to get them all.
        response = self.app.get(url('corpusbackups'), headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert response.content_type == 'application/json'
        assert resp[0]['modifier']['role'] == u'administrator'
        assert resp[1]['modifier']['role'] == u'contributor'

        # The admin should get them all too.
        response = self.app.get(url('corpusbackups'), headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert [cb['id'] for cb in resp] == all_corpus_backup_ids

        # Test the paginator GET params.
        paginator = {'items_per_page': 1, 'page': 2}
        response = self.app.get(url('corpusbackups'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['paginator']['count'] == 2
        assert response.content_type == 'application/json'
        assert resp['items'][0]['id'] == all_corpus_backup_ids[1]

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'CorpusBackup',
            'order_by_attribute': 'id', 'order_by_direction': 'desc'}
        response = self.app.get(url('corpusbackups'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = list(reversed(all_corpus_backup_ids))
        assert [cb['id'] for cb in resp] == result_set

        # Test the order_by *with* paginator.  
        params = {'order_by_model': 'CorpusBackup', 'order_by_attribute': 'id',
                     'order_by_direction': 'desc', 'items_per_page': 1, 'page': 1}
        response = self.app.get(url('corpusbackups'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert result_set[0] == resp['items'][0]['id']

        # Now test the show action:

        # Get a specific corpus backup. 
        response = self.app.get(url('corpusbackup', id=all_corpus_backup_ids[0]),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['description'] == u'Covers a lot of the data.'
        assert resp['content'] == test_corpus_content
        assert response.content_type == 'application/json'

        # A nonexistent cb id will return a 404 error
        response = self.app.get(url('corpusbackup', id=100987),
                    headers=self.json_headers, extra_environ=self.extra_environ_view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no corpus backup with id 100987'
        assert response.content_type == 'application/json'

        # Test the search action
        self._add_SEARCH_to_web_test_valid_methods()

        # A search on corpus backup titles using POST /corpusbackups/search
        json_query = json.dumps({'query': {'filter':
                        ['CorpusBackup', 'description', 'like', u'%less%']}})
        response = self.app.post(url('/corpusbackups/search'), json_query,
                        self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [name for name in all_corpus_backup_descriptions if u'less' in name]
        assert len(resp) == len(result_set) == 1
        assert resp[0]['description'] == result_set[0]
        assert response.content_type == 'application/json'

        # A search on corpus backup titles using SEARCH /corpusbackups
        json_query = json.dumps({'query': {'filter':
                        ['CorpusBackup', 'description', 'like', u'%less%']}})
        response = self.app.request(url('corpusbackups'), method='SEARCH', body=json_query,
                        headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(result_set) == 1
        assert resp[0]['description'] == result_set[0]
        assert response.content_type == 'application/json'

        # Attempting to call edit/new/create/delete/update on a read-only resource
        # will return a 404 response
        response = self.app.get(url('edit_corpusbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.get(url('new_corpusbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.post(url('corpusbackups'), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.put(url('corpusbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.delete(url('corpusbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'

    @nottest
    def test_new_search(self):
        """Tests that GET /corpusbackups/new_search returns the search parameters for searching the corpus backups resource."""
        query_builder = SQLAQueryBuilder('CorpusBackup')
        response = self.app.get(url('/corpusbackups/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['search_parameters'] == h.get_search_parameters(query_builder)
