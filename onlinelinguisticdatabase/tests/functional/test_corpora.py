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

import re
import datetime
import logging
import os
import codecs
import simplejson as json
from uuid import uuid4
from time import sleep
from nose.tools import nottest
from paste.deploy import appconfig
from sqlalchemy.sql import desc
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
import onlinelinguisticdatabase.lib.testutils as testutils
from onlinelinguisticdatabase.model import Corpus, CorpusBackup, CorpusFile
from subprocess import Popen, PIPE, call

log = logging.getLogger(__name__)

class TestCorporaController(TestController):

    config = appconfig('config:test.ini', relative_to='.')
    here = config['here']
    corpusPath = h.getOLDDirectoryPath('corpora', config=config)
    testCorporaPath = os.path.join(here, 'onlinelinguisticdatabase',
                        'tests', 'data', 'corpora')
    testScriptsPath = os.path.join(here, 'onlinelinguisticdatabase',
                        'tests', 'scripts')
    loremipsum100Path = os.path.join(testCorporaPath, 'loremipsum_100.txt')
    loremipsum1000Path = os.path.join(testCorporaPath, 'loremipsum_1000.txt')
    loremipsum10000Path = os.path.join(testCorporaPath, 'loremipsum_10000.txt')

    createParams = testutils.corpusCreateParams
    formCreateParams = testutils.formCreateParams

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language; recreate the corpora.
    def tearDown(self):
        h.clearAllModels()
        h.destroyAllUserDirectories()
        h.destroyAllCorpusDirectories()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that GET /corpora returns an array of all corpora and that orderBy and pagination parameters work correctly."""

        # Add 100 corpora.
        def createCorpusFromIndex(index):
            corpus = model.Corpus()
            corpus.name = u'Corpus %d' % index
            corpus.description = u'A corpus with %d rules' % index
            corpus.content = u'form[1]'
            return corpus
        corpora = [createCorpusFromIndex(i) for i in range(1, 101)]
        Session.add_all(corpora)
        Session.commit()
        corpora = h.getCorpora(True)
        corporaCount = len(corpora)

        # Test that GET /corpora gives us all of the corpora.
        response = self.app.get(url('corpora'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == corporaCount
        assert resp[0]['name'] == u'Corpus 1'
        assert resp[0]['id'] == corpora[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('corpora'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == corpora[46].name
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Corpus', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('corpora'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted(corpora, key=lambda c: c.name, reverse=True)
        assert [c.id for c in resultSet] == [c['id'] for c in resp]
        assert response.content_type == 'application/json'

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Corpus', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('corpora'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46].name == resp['items'][0]['name']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Corpus', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('corpora'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Corpusist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('corpora'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == corpora[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('corpora'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('corpora'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    #@nottest
    def test_create(self):
        """Tests that POST /corpora creates a new corpus
        or returns an appropriate error if the input is invalid.

        """

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
        formCount = len(forms)
        testCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms])
        formIds = [form.id for form in forms]

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
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
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': testCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)

        # Attempt to create a corpus as a viewer and expect to fail
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Successfully create a corpus as the admin
        assert os.listdir(self.corpusPath) == []
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusId = resp['id']
        newCorpusCount = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        assert newCorpusCount == originalCorpusCount + 1
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusContent
        assert sorted([f.id for f in corpus.forms]) == sorted(formIds)
        assert resp['formSearch']['id'] == formSearchId

        # Invalid because ``content`` refers to non-existent forms and ``formSearch``
        # a non-existent form search.
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus Chi',
            'description': u'Covers a lot of the data, padre.',
            'content': testCorpusContent + u'\nform[123456789]',
            'formSearch': 123456789
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        assert newCorpusCount == corpusCount
        assert u'There is no form with id 123456789.' in resp['errors']['forms']
        assert resp['errors']['formSearch'] == u'There is no form search with id 123456789.'
        assert response.content_type == 'application/json'

        # Invalid because name is not unique
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data, dude.',
            'content': testCorpusContent
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        assert newCorpusCount == corpusCount
        assert resp['errors']['name'] == u'The submitted value for Corpus.name is not unique.'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.createParams.copy()
        params.update({
            'name': u'',
            'description': u'Covers a lot of the data, sista.',
            'content': testCorpusContent
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        assert newCorpusCount == corpusCount
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.createParams.copy()
        params.update({
            'name': None,
            'description': u'Covers a lot of the data, young\'un.',
            'content': testCorpusContent
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        assert newCorpusCount == corpusCount
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name is too long.
        params = self.createParams.copy()
        params.update({
            'name': 'Corpus' * 200,
            'description': u'Covers a lot of the data, squirrel salad.',
            'content': testCorpusContent
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        assert newCorpusCount == corpusCount
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    #@nottest
    def test_new(self):
        """Tests that GET /corpora/new returns data needed to create a new corpus."""

        # Create a tag
        t = h.generateRestrictedTag()
        Session.add(t)
        Session.commit()
        tagId = t.id

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
        params = json.dumps({
            'name': u'form search',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        response = self.app.post(url('formsearches'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formSearchId = resp['id']

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'tags': h.getMiniDictsGetter('Tag')(),
            'users': h.getMiniDictsGetter('User')(),
            'formSearches': h.getMiniDictsGetter('FormSearch')(),
            'corpusFormats': h.corpusFormats.keys()
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # Unauthorized user ('viewer') should return a 401 status code on the
        # new action, which requires a 'contributor' or an 'administrator'.
        response = self.app.get(url('new_corpus'), status=403,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

        # Get the data needed to create a new corpus; don't send any params.
        response = self.app.get(url('new_corpus'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['users'] == data['users']
        assert resp['formSearches'] == data['formSearches']
        assert resp['tags'] == data['tags']
        assert resp['corpusFormats'] == data['corpusFormats']
        assert response.content_type == 'application/json'

        # GET /new_corpus with params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetimeModified value of the
        #    store in question.
        params = {
            # Value is any string: 'formSearches' will be in response.
            'formSearches': 'anything can go here!',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Tag.datetimeModified value: 'tags' *will* be in
            # response.
            'tags': datetime.datetime.utcnow().isoformat(),
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent SyntacticCategory.datetimeModified value:
            # 'syntacticCategories' will *not* be in response.
            'users': h.getMostRecentModificationDatetime(
                'User').isoformat()
        }
        response = self.app.get(url('new_corpus'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['formSearches'] == data['formSearches']
        assert resp['tags'] == data['tags']
        assert resp['users'] == []
        assert resp['corpusFormats'] == data['corpusFormats']

    #@nottest
    def test_update(self):
        """Tests that PUT /corpora/id updates the corpus with id=id."""

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
        formCount = len(forms)
        testCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms])
        newTestCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms[:5]])
        formIds = [form.id for form in forms]

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
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
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': testCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)

        # Successfully create a corpus as the admin
        assert os.listdir(self.corpusPath) == []
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusId = resp['id']
        newCorpusCount = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        originalDatetimeModified = resp['datetimeModified']
        assert newCorpusCount == originalCorpusCount + 1
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusContent
        assert sorted([f.id for f in corpus.forms]) == sorted(formIds)
        assert resp['formSearch']['id'] == formSearchId

        # Update the corpus
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        origBackupCount = Session.query(CorpusBackup).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.  Best yet!',
            'content': newTestCorpusContent,        # Here is the change
            'formSearch': formSearchId
        })
        params = json.dumps(params)
        response = self.app.put(url('corpus', id=corpusId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        newBackupCount = Session.query(CorpusBackup).count()
        datetimeModified = resp['datetimeModified']
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        assert corpusCount == newCorpusCount
        assert datetimeModified != originalDatetimeModified
        assert resp['description'] == u'Covers a lot of the data.  Best yet!'
        assert resp['content'] == newTestCorpusContent
        assert response.content_type == 'application/json'
        assert origBackupCount + 1 == newBackupCount
        assert response.content_type == 'application/json'
        backup = Session.query(CorpusBackup).filter(
            CorpusBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(CorpusBackup.id)).first()
        assert backup.datetimeModified.isoformat() == originalDatetimeModified
        assert backup.content == testCorpusContent

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('corpus', id=corpusId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        ourCorpusDatetimeModified = Session.query(Corpus).get(corpusId).datetimeModified
        assert ourCorpusDatetimeModified.isoformat() == datetimeModified
        assert corpusCount == newCorpusCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /corpora/id deletes the corpus with id=id."""

        # Count the original number of corpora and corpusBackups.
        corpusCount = Session.query(Corpus).count()
        corpusBackupCount = Session.query(CorpusBackup).count()

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
        formCount = len(forms)
        testCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms])
        newTestCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms[:5]])
        formIds = [form.id for form in forms]

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
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
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': testCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)

        # Successfully create a corpus as the admin
        assert os.listdir(self.corpusPath) == []
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusId = resp['id']
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusContent
        assert sorted([f.id for f in corpus.forms]) == sorted(formIds)
        assert resp['formSearch']['id'] == formSearchId

        # Now count the corpora and corpusBackups.
        newCorpusCount = Session.query(Corpus).count()
        newCorpusBackupCount = Session.query(CorpusBackup).count()
        assert newCorpusCount == corpusCount + 1
        assert newCorpusBackupCount == corpusBackupCount

        # Now delete the corpus
        response = self.app.delete(url('corpus', id=corpusId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusCount = newCorpusCount
        newCorpusCount = Session.query(Corpus).count()
        corpusBackupCount = newCorpusBackupCount
        newCorpusBackupCount = Session.query(CorpusBackup).count()
        assert newCorpusCount == corpusCount - 1
        assert newCorpusBackupCount == corpusBackupCount + 1
        assert resp['id'] == corpusId
        assert response.content_type == 'application/json'
        assert not os.path.exists(corpusDir)
        assert resp['content'] == testCorpusContent

        # Trying to get the deleted corpus from the db should return None
        deletedCorpus = Session.query(Corpus).get(corpusId)
        assert deletedCorpus == None

        # The backed up corpus should have the deleted corpus's attributes
        backedUpCorpus = Session.query(CorpusBackup).filter(
            CorpusBackup.UUID==unicode(resp['UUID'])).first()
        assert backedUpCorpus.name == resp['name']
        modifier = json.loads(unicode(backedUpCorpus.modifier))
        assert modifier['firstName'] == u'Admin'
        assert backedUpCorpus.datetimeEntered.isoformat() == resp['datetimeEntered']
        assert backedUpCorpus.UUID == resp['UUID']

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('corpus', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no corpus with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('corpus', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_show(self):
        """Tests that GET /corpora/id returns the corpus with id=id or an appropriate error."""

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
        formCount = len(forms)
        testCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms])
        newTestCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms[:5]])
        formIds = [form.id for form in forms]

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
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
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': testCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)

        # Successfully create a corpus as the admin
        assert os.listdir(self.corpusPath) == []
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusCount = Session.query(Corpus).count()
        corpusId = resp['id']
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusContent
        assert sorted([f.id for f in corpus.forms]) == sorted(formIds)
        assert resp['formSearch']['id'] == formSearchId
        assert corpusCount == originalCorpusCount + 1

        # Try to get a corpus using an invalid id
        id = 100000000000
        response = self.app.get(url('corpus', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no corpus with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('corpus', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('corpus', id=corpusId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert resp['content'] == testCorpusContent
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /corpora/id/edit returns a JSON object of data necessary to edit the corpus with id=id.

        The JSON object is of the form {'corpus': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

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
        formCount = len(forms)
        testCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms])
        newTestCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms[:5]])
        formIds = [form.id for form in forms]

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
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
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': testCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)

        # Successfully create a corpus as the admin
        assert os.listdir(self.corpusPath) == []
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusCount = Session.query(Corpus).count()
        corpusId = resp['id']
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusContent
        assert sorted([f.id for f in corpus.forms]) == sorted(formIds)
        assert resp['formSearch']['id'] == formSearchId
        assert corpusCount == originalCorpusCount + 1

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_corpus', id=corpusId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_corpus', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no corpus with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_corpus', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'tags': h.getMiniDictsGetter('Tag')(),
            'users': h.getMiniDictsGetter('User')(),
            'formSearches': h.getMiniDictsGetter('FormSearch')(),
            'corpusFormats': h.corpusFormats.keys()
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # Valid id
        response = self.app.get(url('edit_corpus', id=corpusId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['corpus']['name'] == u'Corpus'
        assert resp['data'] == data
        assert response.content_type == 'application/json'

    #@nottest
    def test_history(self):
        """Tests that GET /corpora/id/history returns the corpus with id=id and its previous incarnations.
        
        The JSON object returned is of the form
        {'corpus': corpus, 'previousVersions': [...]}.

        """

        users = h.getUsers()
        contributorId = [u for u in users if u.role==u'contributor'][0].id
        administratorId = [u for u in users if u.role==u'administrator'][0].id

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
        formCount = len(forms)
        testCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms])
        newTestCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms[:5]])
        newestTestCorpusContent = '\n'.join(['form[%d]' % form.id for form in forms[:4]])
        formIds = [form.id for form in forms]

        # Create a form search model
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
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
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.',
            'content': testCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)

        # Successfully create a corpus as the admin
        assert os.listdir(self.corpusPath) == []
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusCount = Session.query(Corpus).count()
        corpusId = resp['id']
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'Corpus'
        assert resp['description'] == u'Covers a lot of the data.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == testCorpusContent
        assert sorted([f.id for f in corpus.forms]) == sorted(formIds)
        assert resp['formSearch']['id'] == formSearchId
        assert corpusCount == originalCorpusCount + 1

        # Update the corpus as the admin.
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        origBackupCount = Session.query(CorpusBackup).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers a lot of the data.  Best yet!',
            'content': newTestCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)
        response = self.app.put(url('corpus', id=corpusId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        newBackupCount = Session.query(CorpusBackup).count()
        firstUpdateDatetimeModified = datetimeModified = resp['datetimeModified']
        newCorpusCount = Session.query(Corpus).count()
        assert corpusCount == newCorpusCount
        assert datetimeModified != originalDatetimeModified
        assert resp['description'] == u'Covers a lot of the data.  Best yet!'
        assert resp['content'] == newTestCorpusContent
        assert response.content_type == 'application/json'
        assert origBackupCount + 1 == newBackupCount
        backup = Session.query(CorpusBackup).filter(
            CorpusBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(CorpusBackup.id)).first()
        assert backup.datetimeModified.isoformat() == originalDatetimeModified
        assert backup.content == testCorpusContent
        assert json.loads(backup.modifier)['firstName'] == u'Admin'
        assert response.content_type == 'application/json'

        # Update the corpus as the contributor.
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        origBackupCount = Session.query(CorpusBackup).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus',
            'description': u'Covers even more data.  Better than ever!',
            'content': newestTestCorpusContent,
            'formSearch': formSearchId
        })
        params = json.dumps(params)
        response = self.app.put(url('corpus', id=corpusId), params, self.json_headers,
                                 self.extra_environ_contrib)
        resp = json.loads(response.body)
        backupCount = newBackupCount
        newBackupCount = Session.query(CorpusBackup).count()
        datetimeModified = resp['datetimeModified']
        newCorpusCount = Session.query(Corpus).count()
        assert corpusCount == newCorpusCount == 1
        assert datetimeModified != originalDatetimeModified
        assert resp['description'] == u'Covers even more data.  Better than ever!'
        assert resp['content'] == newestTestCorpusContent
        assert resp['modifier']['id'] == contributorId
        assert response.content_type == 'application/json'
        assert backupCount + 1 == newBackupCount
        backup = Session.query(CorpusBackup).filter(
            CorpusBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(CorpusBackup.id)).first()
        assert backup.datetimeModified.isoformat() == firstUpdateDatetimeModified
        assert backup.content == newTestCorpusContent
        assert json.loads(backup.modifier)['firstName'] == u'Admin'
        assert response.content_type == 'application/json'

        # Now get the history of this corpus.
        extra_environ = {'test.authentication.role': u'contributor',
                         'test.applicationSettings': True}
        response = self.app.get(
            url(controller='corpora', action='history', id=corpusId),
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'corpus' in resp
        assert 'previousVersions' in resp
        firstVersion = resp['previousVersions'][1]
        secondVersion = resp['previousVersions'][0]
        currentVersion = resp['corpus']

        assert firstVersion['name'] == u'Corpus'
        assert firstVersion['description'] == u'Covers a lot of the data.'
        assert firstVersion['enterer']['id'] == administratorId
        assert firstVersion['modifier']['id'] == administratorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert firstVersion['datetimeModified'] <= secondVersion['datetimeModified']

        assert secondVersion['name'] == u'Corpus'
        assert secondVersion['description'] == u'Covers a lot of the data.  Best yet!'
        assert secondVersion['content'] == newTestCorpusContent
        assert secondVersion['enterer']['id'] == administratorId
        assert secondVersion['modifier']['id'] == administratorId
        assert secondVersion['datetimeModified'] <= currentVersion['datetimeModified']

        assert currentVersion['name'] == u'Corpus'
        assert currentVersion['description'] == u'Covers even more data.  Better than ever!'
        assert currentVersion['content'] == newestTestCorpusContent
        assert currentVersion['enterer']['id'] == administratorId
        assert currentVersion['modifier']['id'] == contributorId

        # Get the history using the corpus's UUID and expect it to be the same
        # as the one retrieved above
        corpusUUID = resp['corpus']['UUID']
        response = self.app.get(
            url(controller='corpora', action='history', id=corpusUUID),
            headers=self.json_headers, extra_environ=extra_environ)
        respUUID = json.loads(response.body)
        assert resp == respUUID

        # Attempt to call history with an invalid id and an invalid UUID and
        # expect 404 errors in both cases.
        badId = 103
        badUUID = str(uuid4())
        response = self.app.get(
            url(controller='corpora', action='history', id=badId),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No corpora or corpus backups match %d' % badId
        response = self.app.get(
            url(controller='corpora', action='history', id=badUUID),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No corpora or corpus backups match %s' % badUUID

        # Now delete the corpus ...
        response = self.app.delete(url('corpus', id=corpusId),
                        headers=self.json_headers, extra_environ=extra_environ)

        # ... and get its history again, this time using the corpus's UUID
        response = self.app.get(
            url(controller='corpora', action='history', id=corpusUUID),
            headers=self.json_headers, extra_environ=extra_environ)
        byUUIDResp = json.loads(response.body)
        assert byUUIDResp['corpus'] == None
        assert len(byUUIDResp['previousVersions']) == 3
        firstVersion = byUUIDResp['previousVersions'][2]
        secondVersion = byUUIDResp['previousVersions'][1]
        thirdVersion = byUUIDResp['previousVersions'][0]

        assert firstVersion['name'] == u'Corpus'
        assert firstVersion['description'] == u'Covers a lot of the data.'
        assert firstVersion['enterer']['id'] == administratorId
        assert firstVersion['modifier']['id'] == administratorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert firstVersion['datetimeModified'] <= secondVersion['datetimeModified']

        assert secondVersion['name'] == u'Corpus'
        assert secondVersion['description'] == u'Covers a lot of the data.  Best yet!'
        assert secondVersion['content'] == newTestCorpusContent
        assert secondVersion['enterer']['id'] == administratorId
        assert secondVersion['modifier']['id'] == administratorId
        assert secondVersion['datetimeModified'] <= thirdVersion['datetimeModified']

        assert thirdVersion['name'] == u'Corpus'
        assert thirdVersion['description'] == u'Covers even more data.  Better than ever!'
        assert thirdVersion['content'] == newestTestCorpusContent
        assert thirdVersion['enterer']['id'] == administratorId
        assert thirdVersion['modifier']['id'] == contributorId

        # Get the deleted corpus's history again, this time using its id.  The 
        # response should be the same as the response received using the UUID.
        response = self.app.get(
            url(controller='corpora', action='history', id=corpusId),
            headers=self.json_headers, extra_environ=extra_environ)
        byCorpusIdResp = json.loads(response.body)
        assert byCorpusIdResp == byUUIDResp
