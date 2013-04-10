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
        self.addSEARCHToWebTestValidMethods()

    def tearDown(self):
        TestController.tearDown(self, dirsToDestroy=['corpus'])

    #@nottest
    def test_index(self):
        """Tests that GET & SEARCH /corpusbackups behave correctly.
        """

        tag = model.Tag()
        tag.name = u'random tag name'
        Session.add(tag)
        Session.commit()
        tagId = tag.id

        # Add 10 forms and use them to generate a valid value for ``testCorpusContent``
        def createFormFromIndex(index):
            form = model.Form()
            form.transcription = u'Form %d' % index
            translation = model.Translation()
            translation.transcription = u'Translation %d' % index
            form.translation = translation
            return form
        forms = [createFormFromIndex(i) for i in range(1, 10)]
        Session.add_all(forms)
        Session.commit()
        forms = h.getForms()
        halfForms = forms[:5]
        formIds = [form.id for form in forms]
        halfFormIds = [form.id for form in halfForms]
        testCorpusContent = u','.join(map(str, formIds))
        testCorpusHalfContent = u','.join(map(str, halfFormIds))

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
        formSearchId = resp['id']

        # Generate some valid corpus creation input parameters.
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': testCorpusContent
        })
        params = json.dumps(params)

        # Attempt to create a corpus as a viewer and expect to fail
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Successfully create a corpus as the admin
        assert os.listdir(self.corporaPath) == []
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusId = resp['id']
        newCorpusCount = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpusId)
        corpusFormIds = sorted([f.id for f in corpus.forms])
        corpusDir = os.path.join(self.corporaPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        assert newCorpusCount == originalCorpusCount + 1
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusContent
        assert corpusFormIds == sorted(formIds)

        # Update the corpus as the contributor -- now we should have one backup
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a little less data.',
            'content': testCorpusHalfContent
        })
        params = json.dumps(params)
        response = self.app.put(url('corpus', id=corpusId), params,
                self.json_headers, self.extra_environ_contrib)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpusId)
        corpusFormIds = sorted([f.id for f in corpus.forms])
        assert newCorpusCount == corpusCount
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a little less data.' 
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusHalfContent
        assert corpusFormIds == sorted(halfFormIds)

        # Update the corpus again -- now we should have two backups
        sleep(1)
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a little less data.',
            'content': testCorpusHalfContent,
            'tags': [tagId]
        })
        params = json.dumps(params)
        response = self.app.put(url('corpus', id=corpusId), params,
                self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpusId)
        corpusFormIds = sorted([f.id for f in corpus.forms])
        assert newCorpusCount == corpusCount
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a little less data.' 
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusHalfContent
        assert corpusFormIds == sorted(halfFormIds)

        allCorpusBackups = Session.query(CorpusBackup).order_by(CorpusBackup.id).all()
        allCorpusBackupIds = [cb.id for cb in allCorpusBackups]
        allCorpusBackupDescriptions = [cb.description for cb in allCorpusBackups]

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
        assert [cb['id'] for cb in resp] == allCorpusBackupIds

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 1, 'page': 2}
        response = self.app.get(url('corpusbackups'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['paginator']['count'] == 2
        assert response.content_type == 'application/json'
        assert resp['items'][0]['id'] == allCorpusBackupIds[1]

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'CorpusBackup',
            'orderByAttribute': 'id', 'orderByDirection': 'desc'}
        response = self.app.get(url('corpusbackups'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = list(reversed(allCorpusBackupIds))
        assert [cb['id'] for cb in resp] == resultSet

        # Test the orderBy *with* paginator.  
        params = {'orderByModel': 'CorpusBackup', 'orderByAttribute': 'id',
                     'orderByDirection': 'desc', 'itemsPerPage': 1, 'page': 1}
        response = self.app.get(url('corpusbackups'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resultSet[0] == resp['items'][0]['id']

        # Now test the show action:

        # Get a specific corpus backup. 
        response = self.app.get(url('corpusbackup', id=allCorpusBackupIds[0]),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['description'] == u'Covers a lot of the data.'
        assert resp['content'] == testCorpusContent
        assert response.content_type == 'application/json'

        # A nonexistent cb id will return a 404 error
        response = self.app.get(url('corpusbackup', id=100987),
                    headers=self.json_headers, extra_environ=self.extra_environ_view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no corpus backup with id 100987'
        assert response.content_type == 'application/json'

        # Test the search action
        self.addSEARCHToWebTestValidMethods()

        # A search on corpus backup titles using POST /corpusbackups/search
        jsonQuery = json.dumps({'query': {'filter':
                        ['CorpusBackup', 'description', 'like', u'%less%']}})
        response = self.app.post(url('/corpusbackups/search'), jsonQuery,
                        self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [name for name in allCorpusBackupDescriptions if u'less' in name]
        assert len(resp) == len(resultSet) == 1
        assert resp[0]['description'] == resultSet[0]
        assert response.content_type == 'application/json'

        # A search on corpus backup titles using SEARCH /corpusbackups
        jsonQuery = json.dumps({'query': {'filter':
                        ['CorpusBackup', 'description', 'like', u'%less%']}})
        response = self.app.request(url('corpusbackups'), method='SEARCH', body=jsonQuery,
                        headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet) == 1
        assert resp[0]['description'] == resultSet[0]
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

    #@nottest
    def test_new_search(self):
        """Tests that GET /corpusbackups/new_search returns the search parameters for searching the corpus backups resource."""
        queryBuilder = SQLAQueryBuilder('CorpusBackup')
        response = self.app.get(url('/corpusbackups/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['searchParameters'] == h.getSearchParameters(queryBuilder)
