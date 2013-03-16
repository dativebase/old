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
from base64 import encodestring
from paste.deploy import appconfig
from sqlalchemy.sql import desc
from uuid import uuid4
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h

log = logging.getLogger(__name__)


class TestOldcollectionsController(TestController):

    here = appconfig('config:test.ini', relative_to='.')['here']
    filesPath = os.path.join(here, 'files')
    testFilesPath = os.path.join(here, 'test_files')
    reducedFilesPath = os.path.join(filesPath, u'reduced_files')

    createParams = {
        'title': u'',
        'type': u'',
        'url': u'',
        'description': u'',
        'markupLanguage': u'',
        'contents': u'',
        'speaker': u'',
        'source': u'',
        'elicitor': u'',
        'enterer': u'',
        'dateElicited': u'',
        'tags': [],
        'files': []
    }

    createFormParams = {
        'transcription': u'',
        'phoneticTranscription': u'',
        'narrowPhoneticTranscription': u'',
        'morphemeBreak': u'',
        'grammaticality': u'',
        'morphemeGloss': u'',
        'translations': [],
        'comments': u'',
        'speakerComments': u'',
        'elicitationMethod': u'',
        'tags': [],
        'syntacticCategory': u'',
        'speaker': u'',
        'elicitor': u'',
        'verifier': u'',
        'source': u'',
        'status': u'tested',
        'dateElicited': u''     # mm/dd/yyyy
    }

    createFileParams = {
        'name': u'',
        'description': u'',
        'dateElicited': u'',    # mm/dd/yyyy
        'elicitor': u'',
        'speaker': u'',
        'utteranceType': u'',
        'embeddedFileMarkup': u'',
        'embeddedFilePassword': u'',
        'tags': [],
        'forms': [],
        'file': ''      # file data Base64 encoded
    }

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Set up some stuff for the tests
    def setUp(self):
        pass

    def tearDown(self):
        # Clear all models in the database except Language; recreate the users.
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        # Clear the files directory
        h.clearDirectoryOfFiles(self.filesPath)
        h.clearDirectoryOfFiles(self.reducedFilesPath)

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        response = self.app.get(url('forms'), extra_environ=extra_environ)

    #@nottest
    def test_index(self):
        """Tests that GET /collections returns a JSON array of collections with expected values."""

        # Test that the restricted tag is working correctly.
        # First get the users.
        users = h.getUsers()
        administratorId = [u for u in users if u.role == u'administrator'][0].id
        contributorId = [u for u in users if u.role == u'contributor'][0].id
        viewerId = [u for u in users if u.role == u'viewer'][0].id

        # Then add a contributor and a restricted tag.
        restrictedTag = h.generateRestrictedTag()
        myContributor = h.generateDefaultUser()
        myContributorFirstName = u'Mycontributor'
        myContributor.firstName = myContributorFirstName
        Session.add_all([restrictedTag, myContributor])
        Session.commit()
        myContributor = Session.query(model.User).filter(
            model.User.firstName == myContributorFirstName).first()
        myContributorId = myContributor.id
        restrictedTag = h.getRestrictedTag()

        # Then add the default application settings with myContributor as the
        # only unrestricted user.
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.unrestrictedUsers = [myContributor]
        Session.add(applicationSettings)
        Session.commit()

        # Finally, issue two POST requests to create two default collections
        # with the *default* contributor as the enterer.  One collection will be
        # restricted and the other will not be.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}

        # Create the restricted collection.
        params = self.createParams.copy()
        params.update({
            'title': u'Restricted Collection',
            'tags': [h.getTags()[0].id]    # the restricted tag should be the only one
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restrictedCollectionId = resp['id']

        # Create the unrestricted collection.
        params = self.createParams.copy()
        params.update({'title': u'Unrestricted Collection'})
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        unrestrictedCollectionId = resp['id']

        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted myContributor should all be able to view both
        # collections.  The viewer will only receive the unrestricted collection.

        # An administrator should be able to view both collections.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert resp[0]['title'] == u'Restricted Collection'
        assert response.content_type == 'application/json'

        # The default contributor (qua enterer) should also be able to view both
        # collections.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Mycontributor (an unrestricted user) should also be able to view both
        # collections.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # A (not unrestricted) viewer should be able to view only one collection.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove Mycontributor from the unrestricted users list and access to
        # the second collection will be denied.
        applicationSettings = h.getApplicationSettings()
        applicationSettings.unrestrictedUsers = []
        Session.add(applicationSettings)
        Session.commit()

        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view the restricted collection.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True,
                         'test.retainApplicationSettings': True}
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove the restricted tag from the collection and the viewer should
        # now be able to view it too.
        restrictedCollection = Session.query(model.Collection).get(
            restrictedCollectionId)
        restrictedCollection.tags = []
        Session.add(restrictedCollection)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Clear all Collections (actually, everything but the tags, users and
        # languages)
        h.clearAllModels(['User', 'Tag', 'Language'])

        # Now add 100 collections.  The even ones will be restricted, the odd ones not.
        def createCollectionFromIndex(index):
            collection = model.Collection()
            collection.title = u'title %d' % index
            return collection
        collections = [createCollectionFromIndex(i) for i in range(1, 101)]
        Session.add_all(collections)
        Session.commit()
        collections = h.getModelsByName('Collection', True)
        restrictedTag = h.getRestrictedTag()
        for collection in collections:
            if int(collection.title.split(' ')[1]) % 2 == 0:
                collection.tags.append(restrictedTag)
            Session.add(collection)
        Session.commit()
        collections = h.getModelsByName('Collection', True)    # ordered by Collection.id ascending

        # An administrator should be able to retrieve all of the collections.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['title'] == u'title 1'
        assert resp[0]['id'] == collections[0].id

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('collections'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['title'] == collections[46].title

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Collection', 'orderByAttribute': 'title',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('collections'), orderByParams,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        resultSet = sorted([c.title for c in collections], reverse=True)
        assert resultSet == [f['title'] for f in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Collection', 'orderByAttribute': 'title',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('collections'), params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['title']
        assert response.content_type == 'application/json'

        # The default viewer should only be able to see the odd numbered collections,
        # even with a paginator.
        itemsPerPage = 7
        page = 7
        paginator = {'itemsPerPage': itemsPerPage, 'page': page}
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('collections'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == itemsPerPage
        assert resp['items'][0]['title'] == u'title %d' % (
            ((itemsPerPage * (page - 1)) * 2) + 1)

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Collection', 'orderByAttribute': 'title',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('collections'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Collectionissimo', 'orderByAttribute': 'tutelage',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('collections'), orderByParams,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp[0]['id'] == collections[0].id

        # Expect a 400 error when the paginator GET params are, empty, not
        # integers or are integers that are less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('collections'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('collections'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

    #@nottest
    def test_create(self):
        """Tests that POST /collections correctly creates a new collection."""

        # Pass some mal-formed JSON to test that a 400 error is returned.
        params = '"a'   # Bad JSON
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'JSON decode error: the parameters provided were not valid JSON.'

        # Create some test tags
        tag1 = model.Tag()
        tag2 = model.Tag()
        restrictedTag = h.generateRestrictedTag()
        tag1.name = u'tag 1'
        tag2.name = u'tag 2'
        Session.add_all([tag1, tag2, restrictedTag])
        Session.commit()
        tag1Id = tag1.id
        tag2Id = tag2.id
        restrictedTagId = restrictedTag.id

        # Create some test files
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createFileParams.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64EncodedFile': encodestring(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file1Id = resp['id']

        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = encodestring(open(jpgFilePath).read())
        params = self.createFileParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file2Id = resp['id']

        # Create some test forms
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'transcription 1',
            'translations': [{'transcription': u'translation 1', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        form1Id = resp['id']

        params = self.createFormParams.copy()
        params.update({
            'transcription': u'transcription 2',
            'translations': [{'transcription': u'translation 2', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        form2Id = resp['id']

        # Create a test collection.
        mdContents1 = u'\n'.join([
            '### Chapter 1',
            '',
            '#### Section 1',
            '',
            '* Item 1',
            '* Item 2',
            '',
            '#### Section 2',
            '',
            'form[%d]' % form1Id,
            'form[%d]' % form2Id
        ])
        params = self.createParams.copy()
        params.update({
            'title': u'Chapter 1',
            'markupLanguage': u'Markdown',
            'contents': mdContents1,
            'files': [file1Id, file2Id],
            'tags': [tag1Id, tag2Id]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        collection1Id = resp['id']
        collectionCount = Session.query(model.Collection).count()
        assert type(resp) == type({})
        assert resp['title'] == u'Chapter 1'
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['html'] == h.markupLanguageToFunc['Markdown'](mdContents1)
        assert sorted([f['id'] for f in resp['files']]) == sorted([file1Id, file2Id])
        assert sorted([t['id'] for t in resp['tags']]) == sorted([tag1Id, tag2Id])
        assert sorted([f['id'] for f in resp['forms']]) == sorted([form1Id, form2Id])
        assert collectionCount == 1
        assert response.content_type == 'application/json'

        # Create two more forms
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'transcription 3',
            'translations': [{'transcription': u'translation 3', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        form3Id = resp['id']

        params = self.createFormParams.copy()
        params.update({
            'transcription': u'transcription 4',
            'translations': [{'transcription': u'translation 4', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        form4Id = resp['id']

        # Create a second collection, one that references the first.
        mdContents2 = u'\n'.join([
            '## Book 1',
            '',
            'collection[%d]' % collection1Id,
            '',
            '### Chapter 2',
            '',
            'form[%d]' % form3Id
        ])
        params = self.createParams.copy()
        params.update({
            'title': u'Book 1',
            'markupLanguage': u'Markdown',
            'contents': mdContents2
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        collection2Id = resp['id']
        collectionCount = Session.query(model.Collection).count()
        collection2ContentsUnpacked = mdContents2.replace(
            'collection[%d]' % collection1Id, mdContents1)
        assert type(resp) == type({})
        assert resp['title'] == u'Book 1'
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['contentsUnpacked'] == collection2ContentsUnpacked
        assert resp['html'] == h.markupLanguageToFunc['Markdown'](collection2ContentsUnpacked)
        assert resp['files'] == []
        assert resp['tags'] == []
        assert sorted([f['id'] for f in resp['forms']]) == sorted([form1Id, form2Id, form3Id])
        assert collectionCount == 2
        assert response.content_type == 'application/json'

        # Create a third collection, one that references the second and, thereby,
        # the third also.
        mdContents3 = u'\n'.join([
            '# Title',
            '',
            'collection(%d)' % collection2Id,
            '',
            '## Book 2',
            '',
            '### Chapter 3',
            '',
            'form[%d]' % form4Id
        ])
        params3 = self.createParams.copy()
        params3.update({
            'title': u'Novel',
            'markupLanguage': u'Markdown',
            'contents': mdContents3
        })
        params3 = json.dumps(params3)
        response = self.app.post(url('collections'), params3, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        collection3Id = resp['id']
        collectionCount = Session.query(model.Collection).count()
        collection3ContentsUnpacked = mdContents3.replace(
            'collection(%d)' % collection2Id, collection2ContentsUnpacked)
        assert type(resp) == type({})
        assert resp['title'] == u'Novel'
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['contentsUnpacked'] == collection3ContentsUnpacked
        assert resp['html'] == h.markupLanguageToFunc['Markdown'](collection3ContentsUnpacked)
        assert resp['files'] == []
        assert resp['tags'] == []
        assert sorted([f['id'] for f in resp['forms']]) == sorted([form1Id, form2Id, form3Id, form4Id])
        assert collectionCount == 3
        assert response.content_type == 'application/json'

        # First attempt to update the third collection with no new data and
        # expect to fail.
        response = self.app.put(url('collection', id=collection3Id), params3,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The update request failed because the submitted data were not new.'

        # Now update the first collection by restricting it and updating its
        # contents.  Show that these changes propagate up to all collections that
        # reference collection 1 and that the values of the datetimeModified,
        # forms and html (and contentsUnpacked) attributes of these other
        # collections are updated also.
        collection2 = Session.query(model.Collection).get(collection2Id)
        collection2FormIds = [f.id for f in collection2.forms]
        collection2DatetimeModified = collection2.datetimeModified
        collection2HTML = collection2.html
        collection2BackupsCount = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection2Id).count()
        collection3 = Session.query(model.Collection).get(collection3Id)
        collection3FormIds = [f.id for f in collection3.forms]
        collection3DatetimeModified = collection3.datetimeModified
        collection3HTML = collection3.html
        collection3BackupsCount = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection3Id).count()
        sleep(1)
        mdContents1 = u'\n'.join([
            '### Chapter 1',
            '',
            '#### Section 1',
            '',
            '* Item 1',
            '* Item 2',
            '',
            '#### Section 2',
            '',
            'form[%d]' % form2Id    # THE CHANGE: reference to form1 has been removed
        ])
        params = self.createParams.copy()
        params.update({
            'title': u'Chapter 1',
            'markupLanguage': u'Markdown',
            'contents': mdContents1,
            'files': [file1Id, file2Id],
            'tags': [tag1Id, tag2Id, restrictedTagId]   # ANOTHER CHANGE: restrict this collection
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collection1Id), params,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newCollection2 = Session.query(model.Collection).get(collection2Id)
        newCollection2FormIds = [f.id for f in newCollection2.forms]
        newCollection2DatetimeModified = newCollection2.datetimeModified
        newCollection2HTML = newCollection2.html
        newCollection2Contents = newCollection2.contents
        newCollection2Backups = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection2Id).all()
        newCollection2BackupsCount = len(newCollection2Backups)
        newCollection3 = Session.query(model.Collection).get(collection3Id)
        newCollection3FormIds = [f.id for f in newCollection3.forms]
        newCollection3DatetimeModified = newCollection3.datetimeModified
        newCollection3HTML = newCollection3.html
        newCollection3Backups = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection3Id).all()
        newCollection3BackupsCount = len(newCollection3Backups)
        assert form1Id not in [f['id'] for f in resp['forms']]
        assert sorted(collection2FormIds) != sorted(newCollection2FormIds)
        assert form1Id in collection2FormIds
        assert form1Id not in newCollection2FormIds
        assert collection2DatetimeModified != newCollection2DatetimeModified
        assert collection2HTML != newCollection2HTML
        assert sorted(collection3FormIds) != sorted(newCollection3FormIds)
        assert form1Id in collection3FormIds
        assert form1Id not in newCollection3FormIds
        assert collection3DatetimeModified != newCollection3DatetimeModified
        assert collection3HTML != newCollection3HTML
        # Show that backups are made too
        assert newCollection2BackupsCount == collection2BackupsCount + 1
        assert newCollection3BackupsCount == collection3BackupsCount + 1
        assert form1Id not in [f.id for f in newCollection2.forms]
        assert form1Id in json.loads(newCollection2Backups[0].forms)
        assert form1Id not in [f.id for f in newCollection3.forms]
        assert form1Id in json.loads(newCollection3Backups[0].forms)

        # Show that a vacuous update of the third collection with no new data
        # will again fail.
        response = self.app.put(url('collection', id=collection3Id), params3,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The update request failed because the submitted data were not new.'

        # Show how collection deletion propagates.  That is, deleting the first
        # collection will result in a deletion of all references to that collection
        # in the contents of other collections.

        # Delete the first collection and show that the contents value of the
        # second collection no longer references it, i.e., the first.
        response = self.app.delete(url('collection', id=collection1Id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        oldCollection2Contents = newCollection2Contents
        newCollection2 = Session.query(model.Collection).get(collection2Id)
        newCollection2Contents = newCollection2.contents
        collection1Ref = u'collection[%d]' % collection1Id
        oldCollection2BackupsCount = newCollection2BackupsCount
        newCollection2Backups = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection2Id).\
            order_by(desc(model.CollectionBackup.id)).all()
        newCollection2BackupsCount = len(newCollection2Backups)
        assert collection1Ref in oldCollection2Contents
        assert collection1Ref not in newCollection2Contents
        assert newCollection2BackupsCount == oldCollection2BackupsCount + 1
        assert collection1Ref in newCollection2Backups[0].contents

        # Now if we perform an irrelevant update on the third collection, everything
        # will work fine because the reference to the now nonexistent first collection
        # in the contents of the second collection has been removed.  Without deletion
        # propagation, an InvalidCollectionReferenceError would have been raised and
        # an error response would have been returned.
        params3 = json.loads(params3)
        params3.update({u'title': u'A Great Novel'})
        params3 = json.dumps(params3)
        response = self.app.put(url('collection', id=collection3Id), params3,
                                self.json_headers, self.extra_environ_admin)

        # Now show that when a form that is referenced in a collection is deleted,
        # the contents of that collection are edited so that the reference to the
        # deleted form is removed.  This edit causes the appropriate changes to
        # the attributes of the affected collections as well as all of the collections
        # that reference those collections
        collection2 = Session.query(model.Collection).get(collection2Id)
        collection3 = Session.query(model.Collection).get(collection3Id)
        collection2Contents = collection2.contents
        collection2HTML = collection2.html
        collection2Forms = [f.id for f in collection2.forms]
        collection3Forms = [f.id for f in collection3.forms]
        collection3ContentsUnpacked = collection3.contentsUnpacked
        collection3HTML = collection3.html
        collection2BackupsCount = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection2Id).count()
        collection3BackupsCount = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection3Id).count()
        response = self.app.delete(url('form', id=form3Id), headers=self.json_headers,
                                   extra_environ=self.extra_environ_admin)
        newCollection2 = Session.query(model.Collection).get(collection2Id)
        newCollection3 = Session.query(model.Collection).get(collection3Id)
        newCollection2Contents = newCollection2.contents
        newCollection2ContentsUnpacked = newCollection2.contentsUnpacked
        newCollection2Forms = [f.id for f in newCollection2.forms]
        newCollection2HTML = newCollection2.html
        newCollection3Forms = [f.id for f in newCollection3.forms]
        newCollection3ContentsUnpacked = newCollection3.contentsUnpacked
        newCollection3HTML = newCollection3.html
        newCollection2BackupsCount = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection2Id).count()
        newCollection3BackupsCount = Session.query(model.CollectionBackup).\
            filter(model.CollectionBackup.collection_id == collection3Id).count()
        assert 'form[%d]' % form3Id in collection2Contents
        assert 'form[%d]' % form3Id in collection2HTML
        assert 'form[%d]' % form3Id in collection3ContentsUnpacked
        assert 'form[%d]' % form3Id in collection3HTML
        assert 'form[%d]' % form3Id not in newCollection2Contents
        assert 'form[%d]' % form3Id not in newCollection2HTML
        assert 'form[%d]' % form3Id not in newCollection3ContentsUnpacked
        assert 'form[%d]' % form3Id not in newCollection3HTML
        assert form3Id in collection2Forms
        assert form3Id in collection3Forms
        assert form3Id not in newCollection2Forms
        assert form3Id not in newCollection3Forms
        assert newCollection2BackupsCount == collection2BackupsCount + 1
        assert newCollection3BackupsCount == collection3BackupsCount + 1

    #@nottest
    def test_create_invalid(self):
        """Tests that POST /collections with invalid input returns an appropriate error."""

        # Empty title should raise error
        collectionCount = Session.query(model.Collection).count()
        params = self.createParams.copy()
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        assert resp['errors']['title'] == u'Please enter a value'
        assert newCollectionCount == collectionCount

        # Exceeding length restrictions should return errors also.
        params = self.createParams.copy()
        params.update({
            'title': u'test create invalid title' * 100,
            'url': u'test_create_invalid_url' * 100
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        tooLongError = u'Enter a value not more than 255 characters long'
        assert resp['errors']['title'] == tooLongError
        assert resp['errors']['url'] == u'The input is not valid'
        assert newCollectionCount == collectionCount
        assert response.content_type == 'application/json'

        # Add some default application settings and set
        # app_globals.applicationSettings.
        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add(applicationSettings)
        Session.commit()
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True

        # Create a collection with an invalid type, markupLanguage and url
        badURL = u'bad&url'
        badMarkupLanguage = u'rtf'
        badCollectionType = u'novella'
        params = self.createParams.copy()
        params.update({
            'title': u'test create invalid title',
            'url': badURL,
            'markupLanguage': badMarkupLanguage,
            'type': badCollectionType
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        assert resp['errors']['url'] == u'The input is not valid'
        assert resp['errors']['markupLanguage'] == \
            u"Value must be one of: Markdown; reStructuredText (not u'rtf')"
        assert resp['errors']['type'] == \
            u"Value must be one of: story; elicitation; paper; discourse; other (not u'novella')"
        assert newCollectionCount == collectionCount
        assert response.content_type == 'application/json'

        # Create a collection with a valid type, markupLanguage and url
        params = self.createParams.copy()
        params.update({
            'title': u'test create valid title',
            'url': u'good-url/really',
            'markupLanguage': u'reStructuredText',
            'type': u'paper'
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 extra_environ=extra_environ)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        assert resp['url'] == u'good-url/really'
        assert resp['type'] == u'paper'
        assert resp['markupLanguage'] == u'reStructuredText'
        assert newCollectionCount == collectionCount + 1

        # Create a collection with some invalid many-to-one data, i.e., speaker
        # enterer, etc.
        badId = 109
        badInt = u'abc'
        params = self.createParams.copy()
        params.update({
            'title': u'test create invalid title',
            'speaker': badId,
            'elicitor': badInt,
            'source': badInt
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        collectionCount = newCollectionCount
        newCollectionCount = Session.query(model.Collection).count()
        assert resp['errors']['speaker'] == \
            u'There is no speaker with id %d.' % badId
        assert resp['errors']['elicitor'] == u'Please enter an integer value'
        assert resp['errors']['source'] == u'Please enter an integer value'
        assert newCollectionCount == collectionCount
        assert response.content_type == 'application/json'

        # Now create a collection with some *valid* many-to-one data, i.e.,
        # speaker, elicitor, source.
        speaker = h.generateDefaultSpeaker()
        source = h.generateDefaultSource()
        Session.add_all([speaker, source])
        Session.commit()
        contributor = Session.query(model.User).filter(
            model.User.role==u'contributor').first()
        administrator = Session.query(model.User).filter(
            model.User.role==u'administrator').first()
        params = self.createParams.copy()
        params.update({
            'title': u'test create title',
            'speaker': h.getSpeakers()[0].id,
            'elicitor': contributor.id,
            'source': h.getSources()[0].id
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 extra_environ=extra_environ)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        assert resp['source']['year'] == source.year    # etc. ...
        assert resp['speaker']['firstName'] == speaker.firstName
        assert resp['elicitor']['firstName'] == contributor.firstName
        assert newCollectionCount == collectionCount + 1

    #@nottest
    def test_relational_restrictions(self):
        """Tests that the restricted tag works correctly with respect to relational attributes of collections.

        That is, tests that (a) users are not able to access restricted forms or
        files via collection.forms and collection.files respectively since
        collections associated to restricted forms or files are automatically
        tagged as restricted; and (b) a restricted user cannot append a restricted
        form or file to a collection."""

        admin = self.extra_environ_admin.copy()
        admin.update({'test.applicationSettings': True})
        contrib = self.extra_environ_contrib.copy()
        contrib.update({'test.applicationSettings': True})

        # Create a test collection.
        params = self.createParams.copy()
        originalTitle = u'test_update_title'
        params.update({'title': originalTitle})
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        collectionId = int(resp['id'])
        collectionCount = Session.query(model.Collection).count()
        assert resp['title'] == originalTitle
        assert collectionCount == 1

        # Now create the restricted tag.
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTagId = restrictedTag.id

        # Then create two files, one restricted and one not ...
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        wavFileBase64 = encodestring(open(wavFilePath).read())
        params = self.createFileParams.copy()
        params.update({
            'filename': u'restrictedFile.wav',
            'base64EncodedFile': wavFileBase64,
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        restrictedFileId = resp['id']

        params = self.createFileParams.copy()
        params.update({
            'filename': u'unrestrictedFile.wav',
            'base64EncodedFile': wavFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        unrestrictedFileId = resp['id']

        # ... and create two forms, one restricted and one not.
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'restricted',
            'translations': [{'transcription': u'restricted', 'grammaticality': u''}],
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        restrictedFormId = resp['id']

        params = self.createFormParams.copy()
        params.update({
            'transcription': u'unrestricted',
            'translations': [{'transcription': u'unrestricted', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        unrestrictedFormId = resp['id']

        # Now, as a (restricted) contributor, attempt to create a collection and
        # associate it to a restricted file -- expect to fail.
        params = self.createParams.copy()
        params.update({
            'title': u'test',
            'files': [restrictedFileId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the file with id %d.' % restrictedFileId in \
            resp['errors']['files']
        assert response.content_type == 'application/json'

        # Now, as a (restricted) contributor, attempt to create a collection
        # that embeds via reference a restricted form -- expect to fail here also.
        mdContents = u'\n'.join([
            'Chapter',
            '=======',
            '',
            'Section',
            '-------',
            '',
            '* Item 1',
            '* Item 2',
            '',
            'Section containing forms',
            '------------------------',
            '',
            'form[%d]' % restrictedFormId
        ])
        params = self.createParams.copy()
        params.update({
            'title': u'test',
            'markupLanguage': u'Markdown',
            'contents': mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the form with id %d.' % restrictedFormId in \
            resp['errors']['forms']

        # Now, as a (restricted) contributor, attempt to create a collection and
        # associate it to an unrestricted file -- expect to succeed.
        params = self.createParams.copy()
        params.update({
            'title': u'test',
            'files': [unrestrictedFileId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers, contrib)
        resp = json.loads(response.body)
        unrestrictedCollectionId = resp['id']
        assert resp['title'] == u'test'
        assert resp['files'][0]['name'] == u'unrestrictedFile.wav'
        assert response.content_type == 'application/json'

        # Now, as a (restricted) contributor, attempt to create a collection that
        # embeds via reference an unrestricted file -- expect to succeed.
        mdContents = u'\n'.join([
            'Chapter',
            '=======',
            '',
            'Section',
            '-------',
            '',
            '* Item 1',
            '* Item 2',
            '',
            'Section containing forms',
            '------------------------',
            '',
            'form[%d]' % unrestrictedFormId
        ])
        params = self.createParams.copy()
        params.update({
            'title': u'test',
            'markupLanguage': u'Markdown',
            'contents': mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers, contrib)
        resp = json.loads(response.body)
        assert resp['forms'][0]['transcription'] == u'unrestricted'

        # Now, as a(n unrestricted) administrator, attempt to create a collection
        # and associate it to a restricted file -- expect (a) to succeed and (b) to
        # find that the form is now restricted.
        params = self.createParams.copy()
        params.update({
            'title': u'test',
            'files': [restrictedFileId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        indirectlyRestrictedCollection1Id = resp['id']
        assert resp['title'] == u'test'
        assert resp['files'][0]['name'] == u'restrictedFile.wav'
        assert u'restricted' in [t['name'] for t in resp['tags']]
        assert response.content_type == 'application/json'

        # Now, as a(n unrestricted) administrator, attempt to create a collection
        # that embeds via reference a restricted form -- expect to succeed here also.
        mdContents = u'\n'.join([
            'Chapter',
            '=======',
            '',
            'Section',
            '-------',
            '',
            '* Item 1',
            '* Item 2',
            '',
            'Section containing forms',
            '------------------------',
            '',
            'form[%d]' % restrictedFormId
        ])
        params = self.createParams.copy()
        params.update({
            'title': u'test',
            'markupLanguage': u'Markdown',
            'contents': mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        indirectlyRestrictedCollection2Id = resp['id']
        assert resp['title'] == u'test'
        assert resp['forms'][0]['transcription'] == u'restricted'
        assert u'restricted' in [t['name'] for t in resp['tags']]
        assert response.content_type == 'application/json'

        # Now show that the indirectly restricted collections are inaccessible to
        # unrestricted users.
        response = self.app.get(url('collections'), headers=self.json_headers,
                                extra_environ=contrib)
        resp = json.loads(response.body)
        assert indirectlyRestrictedCollection1Id not in [c['id'] for c in resp]
        assert indirectlyRestrictedCollection2Id not in [c['id'] for c in resp]

        # Now, as a(n unrestricted) administrator, create a collection.
        unrestrictedCollectionParams = self.createParams.copy()
        unrestrictedCollectionParams.update({'title': u'test'})
        params = json.dumps(unrestrictedCollectionParams)
        response = self.app.post(url('collections'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        unrestrictedCollectionId = resp['id']
        assert resp['title'] == u'test'

        # As a restricted contributor, attempt to update the unrestricted collection
        # just created by associating it to a restricted file -- expect to fail.
        unrestrictedCollectionParams.update({'files': [restrictedFileId]})
        params = json.dumps(unrestrictedCollectionParams)
        response = self.app.put(url('collection', id=unrestrictedCollectionId), params,
                                self.json_headers, contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the file with id %d.' % restrictedFileId in \
            resp['errors']['files']

        # As an unrestricted administrator, attempt to update an unrestricted collection
        # by associating it to a restricted file -- expect to succeed.
        response = self.app.put(url('collection', id=unrestrictedCollectionId), params,
                                self.json_headers, admin)
        resp = json.loads(response.body)
        assert resp['id'] == unrestrictedCollectionId
        assert u'restricted' in [t['name'] for t in resp['tags']]
        assert response.content_type == 'application/json'

        # Now show that the newly indirectly restricted collection is also
        # inaccessible to an unrestricted user.
        response = self.app.get(url('collection', id=unrestrictedCollectionId),
                headers=self.json_headers, extra_environ=contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        h.clearDirectoryOfFiles(self.filesPath)

    #@nottest
    def test_new(self):
        """Tests that GET /collection/new returns an appropriate JSON object for creating a new OLD collection.

        The properties of the JSON object are 'speakers', 'users', 'tags',
        'sources', 'collectionTypes', 'markupLanguages' and their values are
        arrays/lists.
        """

        # Unauthorized user ('viewer') should return a 401 status code on the
        # new action, which requires a 'contributor' or an 'administrator'.
        extra_environ = {'test.authentication.role': 'viewer'}
        response = self.app.get(url('new_collection'), extra_environ=extra_environ,
                                status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        foreignWordTag = h.generateForeignWordTag()
        restrictedTag = h.generateRestrictedTag()
        speaker = h.generateDefaultSpeaker()
        source = h.generateDefaultSource()
        Session.add_all([applicationSettings, foreignWordTag, restrictedTag,
                         speaker, source])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'speakers': h.getMiniDictsGetter('Speaker')(),
            'users': h.getMiniDictsGetter('User')(),
            'tags': h.getMiniDictsGetter('Tag')(),
            'sources': h.getMiniDictsGetter('Source')()
        }

        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # GET /collection/new without params.  Without any GET params,
        # /collection/new should return a JSON array for every store.
        response = self.app.get(url('new_collection'),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['tags'] == data['tags']
        assert resp['speakers'] == data['speakers']
        assert resp['users'] == data['users']
        assert resp['sources'] == data['sources']
        assert set(resp['collectionTypes']) == set(h.collectionTypes)
        assert set(resp['markupLanguages']) == set(h.markupLanguages)
        assert response.content_type == 'application/json'

        # GET /new_collection with params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetimeModified value of the
        #    store in question.
        params = {
            # Value is empty string: 'speakers' will not be in response.
            'speakers': '',
            # Value is any string: 'sources' will be in response.
            'sources': 'anything can go here!',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Tag.datetimeModified value: 'tags' *will* be in
            # response.
            'tags': datetime.datetime.utcnow().isoformat(),
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent SyntacticCategory.datetimeModified value:
            # 'syntacticCategories' will *not* be in response.
            'users': h.getMostRecentModificationDatetime('User').isoformat()
        }
        response = self.app.get(url('new_collection'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['speakers'] == []
        assert resp['sources'] == data['sources']
        assert resp['tags'] == data['tags']
        assert resp['users'] == []
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /collections/id correctly updates an existing collection."""

        collectionCount = Session.query(model.Collection).count()

        # Add the default application settings and the restricted tag.
        restrictedTag = h.generateRestrictedTag()
        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add_all([applicationSettings, restrictedTag])
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        restrictedTagId = restrictedTag.id

        # Create a collection to update.
        params = self.createParams.copy()
        originalTitle = u'test_update_title'
        params.update({
            'title': originalTitle,
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        id = int(resp['id'])
        newCollectionCount = Session.query(model.Collection).count()
        assert resp['title'] == originalTitle
        assert newCollectionCount == collectionCount + 1

        # As a viewer, attempt to update the restricted collection we just created.
        # Expect to fail.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({'title': u'Updated!'})
        params = json.dumps(params)
        response = self.app.put(url('collection', id=id), params,
            self.json_headers, extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        # As a restricted contributor, attempt to update the restricted
        # collection we just created.  Expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({'title': u'Updated!'})
        params = json.dumps(params)
        response = self.app.put(url('collection', id=id), params,
            self.json_headers, extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # As an administrator now, update the collection just created and expect to
        # succeed.
        origBackupCount = Session.query(model.CollectionBackup).count()
        params = self.createParams.copy()
        params.update({'title': u'Updated!'})
        params = json.dumps(params)
        response = self.app.put(url('collection', id=id), params,
                                self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        newBackupCount = Session.query(model.CollectionBackup).count()
        assert resp['title'] == u'Updated!'
        assert newCollectionCount == collectionCount + 1
        assert origBackupCount + 1 == newBackupCount
        backup = Session.query(model.CollectionBackup).filter(
            model.CollectionBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(model.CollectionBackup.id)).first()
        assert backup.datetimeModified.isoformat() == resp['datetimeModified']
        assert backup.title == originalTitle
        assert response.content_type == 'application/json'

        # Attempt an update with no new data.  Expect a 400 error
        # and response['errors'] = {'no change': The update request failed
        # because the submitted data were not new.'}.
        origBackupCount = Session.query(model.CollectionBackup).count()
        response = self.app.put(url('collection', id=id), params, self.json_headers,
                                self.extra_environ_admin, status=400)
        newBackupCount = Session.query(model.CollectionBackup).count()
        resp = json.loads(response.body)
        assert origBackupCount == newBackupCount
        assert u'the submitted data were not new' in resp['error']
        assert response.content_type == 'application/json'

        # Now update our form by adding a many-to-one datum, viz. a speaker
        speaker = h.generateDefaultSpeaker()
        Session.add(speaker)
        Session.commit()
        speaker = h.getSpeakers()[0]
        speakerId = speaker.id
        speakerFirstName = speaker.firstName
        params = self.createParams.copy()
        params.update({
            'title': u'Another title',
            'speaker': speakerId
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=id), params, self.json_headers,
                                 extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp['speaker']['firstName'] == speakerFirstName
        assert response.content_type == 'application/json'

        # Test the updating of many-to-many data.

        collectionCountAtStart = Session.query(model.Collection).count()

        # Create some more tags
        tag1 = model.Tag()
        tag2 = model.Tag()
        tag1.name = u'tag 1'
        tag2.name = u'tag 2'
        Session.add_all([tag1, tag2])
        Session.commit()
        tag1Id = tag1.id
        tag2Id = tag2.id

        # Create some test files
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createFileParams.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64EncodedFile': encodestring(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file1Id = resp['id']

        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = encodestring(open(jpgFilePath).read())
        params = self.createFileParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file2Id = resp['id']

        # Create some test forms
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'transcription 1',
            'translations': [{'transcription': u'translation 1', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        form1Id = resp['id']

        params = self.createFormParams.copy()
        params.update({
            'transcription': u'transcription 2',
            'translations': [{'transcription': u'translation 2', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        form2Id = resp['id']

        # Create a test collection.
        mdContents = u'\n'.join([
            'Chapter',
            '=======',
            '',
            'Section',
            '-------',
            '',
            '* Item 1',
            '* Item 2',
            '',
            'Section containing forms',
            '------------------------',
            '',
            'form[%d]' % form1Id,
            'form[%d]' % form2Id
        ])
        params = self.createParams.copy()
        params.update({
            'title': u'test_create_title',
            'markupLanguage': u'Markdown',
            'contents': mdContents,
            'files': [file1Id, file2Id],
            'tags': [restrictedTagId, tag1Id, tag2Id]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        createdCollectionId = resp['id']
        collectionCount = Session.query(model.Collection).count()
        assert resp['title'] == u'test_create_title'
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['html'] == h.markupLanguageToFunc['Markdown'](mdContents)
        assert sorted([f['id'] for f in resp['files']]) == sorted([file1Id, file2Id])
        assert sorted([t['id'] for t in resp['tags']]) == sorted([tag1Id, tag2Id, restrictedTagId])
        assert sorted([f['id'] for f in resp['forms']]) == sorted([form1Id, form2Id])
        assert collectionCount == collectionCountAtStart + 1
        assert response.content_type == 'application/json'

        # Attempt to update the collection we just created by merely changing the
        # order of the ids for the many-to-many attributes -- expect to fail.
        tags = [t.id for t in h.getTags()]
        tags.reverse()
        files = [f.id for f in h.getFiles()]
        files.reverse()
        params = self.createParams.copy()
        params.update({
            'title': u'test_create_title',
            'markupLanguage': u'Markdown',
            'contents': mdContents,
            'tags': tags,
            'files': files
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=createdCollectionId), params,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Now update by removing one of the files and expect success.
        params = self.createParams.copy()
        params.update({
            'title': u'test_create_title',
            'markupLanguage': u'Markdown',
            'contents': mdContents,
            'tags': tags,
            'files': files[0:1]
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=createdCollectionId), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        assert newCollectionCount == collectionCount
        assert len(resp['files']) == 1
        assert restrictedTag.name in [t['name'] for t in resp['tags']]
        assert response.content_type == 'application/json'

        # Attempt to create a form with some *invalid* files and tags and fail.
        params = self.createParams.copy()
        params.update({
            'title': u'test_create_title',
            'markupLanguage': u'Markdown',
            'contents': mdContents,
            'tags': [1000, 9875, u'abcdef'],
            'files': [44, u'1t']
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        collectionCount = newCollectionCount
        newCollectionCount = Session.query(model.Collection).count()
        resp = json.loads(response.body)
        assert newCollectionCount == collectionCount
        assert u'Please enter an integer value' in resp['errors']['files']
        assert u'There is no file with id 44.' in resp['errors']['files']
        assert u'There is no tag with id 1000.' in resp['errors']['tags']
        assert u'There is no tag with id 9875.' in resp['errors']['tags']
        assert u'Please enter an integer value' in resp['errors']['tags']
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /collections/id deletes the collection with id=id and returns a JSON representation.

        If the id is invalid or unspecified, then JSON null or a 404 status code
        are returned, respectively.
        """

        originalContributorId = Session.query(model.User).filter(
            model.User.role==u'contributor').first().id
        # Add some objects to the db: a default application settings, a speaker,
        # a tag, a file ...
        applicationSettings = h.generateDefaultApplicationSettings()
        speaker = h.generateDefaultSpeaker()
        myContributor = h.generateDefaultUser()
        myContributor.username = u'uniqueusername'
        tag = model.Tag()
        tag.name = u'default tag'
        file = h.generateDefaultFile()
        Session.add_all([applicationSettings, speaker, myContributor, tag, file])
        Session.commit()
        myContributor = Session.query(model.User).filter(
            model.User.username==u'uniqueusername').first()
        myContributorId = myContributor.id
        myContributorFirstName = myContributor.firstName
        tagId = tag.id
        fileId = file.id
        speakerId = speaker.id
        speakerFirstName = speaker.firstName

        # Add a form for testing
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'test_delete_transcription',
            'translations': [{'transcription': u'test_delete_translation', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        formId = resp['id']

        # Count the original number of collections and collectionBackups.
        collectionCount = Session.query(model.Collection).count()
        collectionBackupCount = Session.query(model.CollectionBackup).count()

        # First, as myContributor, create a collection to delete.
        mdContents = u'\n'.join([
            'Chapter',
            '=======',
            '',
            'Section',
            '-------',
            '',
            '* Item 1',
            '* Item 2',
            '',
            'Section containing forms',
            '------------------------',
            '',
            'form[%d]' % formId
        ])
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'title': u'Test Delete',
            'speaker': speakerId,
            'tags': [tagId],
            'files': [fileId],
            'markupLanguage': u'Markdown',
            'contents': mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        toDeleteId = resp['id']
        assert resp['title'] == u'Test Delete'
        assert resp['speaker']['firstName'] == speakerFirstName
        assert resp['tags'][0]['name'] == u'default tag'
        assert resp['files'][0]['name'] == u'test_file_name'
        assert resp['forms'][0]['transcription'] == u'test_delete_transcription'

        # Now count the collections and collectionBackups.
        newCollectionCount = Session.query(model.Collection).count()
        newCollectionBackupCount = Session.query(model.CollectionBackup).count()
        assert newCollectionCount == collectionCount + 1
        assert newCollectionBackupCount == collectionBackupCount

        # Now, as the default contributor, attempt to delete the myContributor-
        # entered collection we just created and expect to fail.
        extra_environ = {'test.authentication.id': originalContributorId,
                         'test.applicationSettings': True}
        response = self.app.delete(url('collection', id=toDeleteId),
                                   extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # As myContributor, attempt to delete the collection we just created and
        # expect to succeed.  Show that models related via many-to-many relations
        # (e.g., tags and files) and via many-to-one relations (e.g., speakers)
        # are not deleted.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.delete(url('collection', id=toDeleteId),
                                   extra_environ=extra_environ)
        resp = json.loads(response.body)
        newCollectionCount = Session.query(model.Collection).count()
        newCollectionBackupCount = Session.query(model.CollectionBackup).count()
        tagOfDeletedCollection = Session.query(model.Tag).get(
            resp['tags'][0]['id'])
        fileOfDeletedCollection = Session.query(model.File).get(
            resp['files'][0]['id'])
        speakerOfDeletedCollection = Session.query(model.Speaker).get(
            resp['speaker']['id'])
        assert isinstance(tagOfDeletedCollection, model.Tag)
        assert isinstance(fileOfDeletedCollection, model.File)
        assert isinstance(speakerOfDeletedCollection, model.Speaker)
        assert newCollectionCount == collectionCount
        assert newCollectionBackupCount == collectionBackupCount + 1
        assert response.content_type == 'application/json'

        # The deleted collection will be returned to us, so the assertions from above
        # should still hold true.
        assert resp['title'] == u'Test Delete'

        # Trying to get the deleted collection from the db should return None
        deletedCollection = Session.query(model.Collection).get(toDeleteId)
        assert deletedCollection == None

        # The backed up collection should have the deleted collection's attributes
        backedUpCollection = Session.query(model.CollectionBackup).filter(
            model.CollectionBackup.UUID==unicode(resp['UUID'])).first()
        assert backedUpCollection.title == resp['title']
        modifier = json.loads(unicode(backedUpCollection.modifier))
        assert modifier['firstName'] == myContributorFirstName
        backedUpSpeaker = json.loads(unicode(backedUpCollection.speaker))
        assert backedUpSpeaker['firstName'] == speakerFirstName
        assert backedUpCollection.datetimeEntered.isoformat() == resp['datetimeEntered']
        assert backedUpCollection.UUID == resp['UUID']
        assert response.content_type == 'application/json'

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('collection', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no collection with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('collection', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_show(self):
        """Tests that GET /collection/id returns a JSON collection object, null or 404
        depending on whether the id is valid, invalid or unspecified, respectively.
        """

        # First add a collection.
        collection = model.Collection()
        collection.title = u'Title'
        Session.add(collection)
        Session.commit()
        collectionId = h.getModelsByName('Collection')[0].id

        # Invalid id
        id = 100000000000
        response = self.app.get(url('collection', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no collection with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('collection', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('collection', id=collectionId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['title'] == u'Title'
        assert response.content_type == 'application/json'

        # Now test that the restricted tag is working correctly.
        # First get the default contributor's id.
        users = h.getUsers()
        contributorId = [u for u in users if u.role == u'contributor'][0].id

        # Then add another contributor and a restricted tag.
        restrictedTag = h.generateRestrictedTag()
        myContributor = h.generateDefaultUser()
        myContributorFirstName = u'Mycontributor'
        myContributor.firstName = myContributorFirstName
        myContributor.username = u'uniqueusername'
        Session.add_all([restrictedTag, myContributor])
        Session.commit()
        myContributorId = myContributor.id
        restrictedTagId = restrictedTag.id

        # Then add the default application settings with myContributor as the
        # only unrestricted user.
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.unrestrictedUsers = [myContributor]
        Session.add(applicationSettings)
        Session.commit()
        # Finally, issue a POST request to create the restricted collection with
        # the *default* contributor as the enterer.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'title': u'Test Restricted Tag',
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restrictedCollectionId = resp['id']
        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted myContributor should all be able to view the collection.
        # The viewer should get a 403 error when attempting to view this collection.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('collection', id=restrictedCollectionId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # The default contributor (qua enterer) should be able to view this collection.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('collection', id=restrictedCollectionId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # Mycontributor (an unrestricted user) should be able to view this
        # restricted collection.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('collection', id=restrictedCollectionId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # A (not unrestricted) viewer should *not* be able to view this collection.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('collection', id=restrictedCollectionId),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        # Remove Mycontributor from the unrestricted users list and access will be denied.
        applicationSettings = h.getApplicationSettings()
        applicationSettings.unrestrictedUsers = []
        Session.add(applicationSettings)
        Session.commit()
        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view this restricted collection.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('collection', id=restrictedCollectionId),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        assert response.content_type == 'application/json'

        # Remove the restricted tag from the collection and the viewer should now be
        # able to view it too.
        restrictedCollection = Session.query(model.Collection).get(restrictedCollectionId)
        restrictedCollection.tags = []
        Session.add(restrictedCollection)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('collection', id=restrictedCollectionId),
                        headers=self.json_headers, extra_environ=extra_environ)
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /collections/id/edit returns a JSON object of data necessary to edit the collection with id=id.

        The JSON object is of the form {'collection': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Add the default application settings and the restricted tag.
        applicationSettings = h.generateDefaultApplicationSettings()
        restrictedTag = h.generateRestrictedTag()
        Session.add_all([restrictedTag, applicationSettings])
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        # Create a restricted collection.
        collection = model.Collection()
        collection.title = u'Test'
        collection.tags = [restrictedTag]
        Session.add(collection)
        Session.commit()
        restrictedCollectionId = collection.id

        # As a (not unrestricted) contributor, attempt to call edit on the
        # restricted collection and expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.applicationSettings': True}
        response = self.app.get(url('edit_collection', id=restrictedCollectionId),
                                extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_collection', id=restrictedCollectionId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_collection', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no collection with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_collection', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_collection', id=restrictedCollectionId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['collection']['title'] == u'Test'
        assert response.content_type == 'application/json'

        # Valid id with GET params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetimeModified value of the
        #    store in question.

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        foreignWordTag = h.generateForeignWordTag()
        speaker = h.generateDefaultSpeaker()
        source = h.generateDefaultSource()
        Session.add_all([applicationSettings, foreignWordTag, speaker, source])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'speakers': h.getMiniDictsGetter('Speaker')(),
            'users': h.getMiniDictsGetter('User')(),
            'tags': h.getMiniDictsGetter('Tag')(),
            'sources': h.getMiniDictsGetter('Source')()
        }

        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        params = {
            # Value is a non-empty string: 'tags' will be in response.
            'tags': 'give me some tags!',
            # Value is empty string: 'speakers' will not be in response.
            'speakers': '',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Source.datetimeModified value: 'sources' *will* be in
            # response.
            'sources': datetime.datetime.utcnow().isoformat(),
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent User.datetimeModified value: 'users' will *not* be in response.
            'users': h.getMostRecentModificationDatetime('User').isoformat()
        }
        response = self.app.get(url('edit_collection', id=restrictedCollectionId), params,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['data']['tags'] == data['tags']
        assert resp['data']['speakers'] == []
        assert resp['data']['users'] == []
        assert resp['data']['sources'] == data['sources']
        assert set(resp['data']['collectionTypes']) == set(h.collectionTypes)
        assert set(resp['data']['markupLanguages']) == set(h.markupLanguages)
        assert response.content_type == 'application/json'

        # Invalid id with GET params.  It should still return 'null'.
        params = {
            # If id were valid, this would cause a speakers array to be returned
            # also.
            'speakers': 'True',
        }
        response = self.app.get(url('edit_collection', id=id), params,
                            extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no collection with id %s' % id in json.loads(response.body)['error']

    #@nottest
    def test_history(self):
        """Tests that GET /collections/id/history returns the collection with id=id and its previous incarnations.

        The JSON object returned is of the form
        {'collection': collection, 'previousVersions': [...]}.
        """

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        source = h.generateDefaultSource()
        restrictedTag = h.generateRestrictedTag()
        file1 = h.generateDefaultFile()
        file1.name = u'file1'
        file2 = h.generateDefaultFile()
        file2.name = u'file2'
        speaker = h.generateDefaultSpeaker()
        Session.add_all([applicationSettings, source, restrictedTag, file1,
                         file2, speaker])
        Session.commit()
        speakerId = speaker.id
        restrictedTagId = restrictedTag.id
        tagIds = [restrictedTagId]
        file1Id = file1.id
        file2Id = file2.id
        fileIds = [file1Id, file2Id]

        # Create a restricted collection (via request) as the default contributor
        users = h.getUsers()
        contributorId = [u for u in users if u.role==u'contributor'][0].id
        administratorId = [u for u in users if u.role==u'administrator'][0].id

        extra_environ = {'test.authentication.role': u'contributor',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'title': u'Created by the Contributor',
            'elicitor': contributorId,
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                        extra_environ)
        collectionCount = Session.query(model.Collection).count()
        resp = json.loads(response.body)
        collectionId = resp['id']
        collectionUUID = resp['UUID']
        assert collectionCount == 1
        assert response.content_type == 'application/json'

        # Update our collection (via request) as the default administrator
        extra_environ = {'test.authentication.role': u'administrator',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'url': u'find/me/here',
            'title': u'Updated by the Administrator',
            'speaker': speakerId,
            'tags': tagIds + [None, u''], # None and u'' ('') will be ignored by collections.updateCollection
            'enterer': administratorId  # This should change nothing.
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collectionId), params,
                        self.json_headers, extra_environ)
        resp = json.loads(response.body)
        collectionCount = Session.query(model.Collection).count()
        assert collectionCount == 1
        assert response.content_type == 'application/json'

        # Finally, update our collection (via request) as the default contributor.
        extra_environ = {'test.authentication.role': u'contributor',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'title': u'Updated by the Contributor',
            'speaker': speakerId,
            'tags': tagIds,
            'files': fileIds
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collectionId), params,
                        self.json_headers, extra_environ)
        resp = json.loads(response.body)
        collectionCount = Session.query(model.Collection).count()
        assert collectionCount == 1
        assert response.content_type == 'application/json'

        # Now get the history of this collection.
        extra_environ = {'test.authentication.role': u'contributor',
                         'test.applicationSettings': True}
        response = self.app.get(
            url(controller='oldcollections', action='history', id=collectionId),
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert 'collection' in resp
        assert 'previousVersions' in resp
        firstVersion = resp['previousVersions'][1]
        secondVersion = resp['previousVersions'][0]
        currentVersion = resp['collection']
        assert firstVersion['title'] == u'Created by the Contributor'
        assert firstVersion['elicitor']['id'] == contributorId
        assert firstVersion['enterer']['id'] == contributorId
        assert firstVersion['modifier']['id'] == contributorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert firstVersion['datetimeModified'] <= secondVersion['datetimeModified']
        assert firstVersion['speaker'] == None
        assert [t['id'] for t in firstVersion['tags']] == [restrictedTagId]
        assert firstVersion['files'] == []
        assert response.content_type == 'application/json'

        assert secondVersion['title'] == u'Updated by the Administrator'
        assert secondVersion['elicitor'] == None
        assert secondVersion['enterer']['id'] == contributorId
        assert secondVersion['modifier']['id'] == administratorId
        assert secondVersion['datetimeModified'] == currentVersion['datetimeModified']
        assert secondVersion['speaker']['id'] == speakerId
        assert sorted([t['id'] for t in secondVersion['tags']]) == sorted(tagIds)
        assert secondVersion['files'] == []

        assert currentVersion['title'] == u'Updated by the Contributor'
        assert currentVersion['elicitor'] == None
        assert currentVersion['enterer']['id'] == contributorId
        assert currentVersion['speaker']['id'] == speakerId
        assert currentVersion['modifier']['id'] == contributorId
        assert sorted([t['id'] for t in currentVersion['tags']]) == sorted(tagIds)
        assert sorted([f['id'] for f in currentVersion['files']]) == sorted(fileIds)

        # Attempt to get the history of the just-entered restricted collection as a
        # viewer and expect to fail with 403.
        extra_environ_viewer = {'test.authentication.role': u'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(
            url(controller='oldcollections', action='history', id=collectionId),
            headers=self.json_headers, extra_environ=extra_environ_viewer,
            status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        # Attempt to call history with an invalid id and an invalid UUID and
        # expect 404 errors in both cases.
        badId = 103
        badUUID = str(uuid4())
        response = self.app.get(
            url(controller='oldcollections', action='history', id=badId),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No collections or collection backups match %d' % badId
        response = self.app.get(
            url(controller='oldcollections', action='history', id=badUUID),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No collections or collection backups match %s' % badUUID

        # Now delete the collection ...
        response = self.app.delete(url('collection', id=collectionId),
                        headers=self.json_headers, extra_environ=extra_environ)

        # ... and get its history again, this time using the collection's UUID
        response = self.app.get(
            url(controller='oldcollections', action='history', id=collectionUUID),
            headers=self.json_headers, extra_environ=extra_environ)
        byUUIDResp = json.loads(response.body)
        assert byUUIDResp['collection'] == None
        assert len(byUUIDResp['previousVersions']) == 3
        firstVersion = byUUIDResp['previousVersions'][2]
        secondVersion = byUUIDResp['previousVersions'][1]
        thirdVersion = byUUIDResp['previousVersions'][0]
        assert firstVersion['title'] == u'Created by the Contributor'
        assert firstVersion['elicitor']['id'] == contributorId
        assert firstVersion['enterer']['id'] == contributorId
        assert firstVersion['modifier']['id'] == contributorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert firstVersion['datetimeModified'] <= secondVersion['datetimeModified']
        assert firstVersion['speaker'] == None
        assert [t['id'] for t in firstVersion['tags']] == [restrictedTagId]
        assert firstVersion['files'] == []

        assert secondVersion['title'] == u'Updated by the Administrator'
        assert secondVersion['elicitor'] == None
        assert secondVersion['enterer']['id'] == contributorId
        assert secondVersion['modifier']['id'] == administratorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert secondVersion['datetimeModified'] <= thirdVersion['datetimeModified']
        assert secondVersion['speaker']['id'] == speakerId
        assert sorted([t['id'] for t in secondVersion['tags']]) == sorted(tagIds)
        assert secondVersion['files'] == []

        assert thirdVersion['title'] == u'Updated by the Contributor'
        assert thirdVersion['elicitor'] == None
        assert thirdVersion['enterer']['id'] == contributorId
        assert thirdVersion['modifier']['id'] == contributorId
        assert thirdVersion['speaker']['id'] == speakerId
        assert sorted([t['id'] for t in thirdVersion['tags']]) == sorted(tagIds)
        assert sorted([f['id'] for f in thirdVersion['files']]) == sorted(fileIds)

        # Get the deleted collection's history again, this time using its id.  The 
        # response should be the same as the response received using the UUID.
        response = self.app.get(
            url(controller='oldcollections', action='history', id=collectionId),
            headers=self.json_headers, extra_environ=extra_environ)
        byCollectionIdResp = json.loads(response.body)
        assert byCollectionIdResp == byUUIDResp

        # Create a new restricted collection as an administrator.
        params = self.createParams.copy()
        params.update({
            'title': u'2nd collection restricted',
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers,
                        self.extra_environ_admin)
        resp = json.loads(response.body)
        collectionCount = Session.query(model.Collection).count()
        collectionId = resp['id']
        collectionUUID = resp['UUID']
        assert collectionCount == 1

        # Update the just-created collection by removing the restricted tag.
        params = self.createParams.copy()
        params.update({
            'title': u'2nd collection unrestricted',
            'tags': []
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collectionId), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        # Now update it in another way.
        params = self.createParams.copy()
        params.update({
            'title': u'2nd collection unrestricted updated',
            'tags': []
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collectionId), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        # Get the history of the just-entered restricted collection as a
        # contributor and expect to receive only the '2nd collection' version in the
        # previousVersions.
        response = self.app.get(
            url(controller='oldcollections', action='history', id=collectionId),
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['previousVersions']) == 1
        assert resp['previousVersions'][0]['title'] == \
            u'2nd collection unrestricted'
        assert resp['collection']['title'] == u'2nd collection unrestricted updated'
        assert response.content_type == 'application/json'

        # Now get the history of the just-entered restricted collection as an
        # administrator and expect to receive both backups.
        response = self.app.get(
            url(controller='oldcollections', action='history', id=collectionId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp['previousVersions']) == 2
        assert resp['previousVersions'][0]['title'] == \
            u'2nd collection unrestricted'
        assert resp['previousVersions'][1]['title'] == \
            u'2nd collection restricted'
        assert resp['collection']['title'] == u'2nd collection unrestricted updated'
        assert response.content_type == 'application/json'

    #@nottest
    def test_new_search(self):
        """Tests that GET /collections/new_search returns the search parameters for searching the collections resource."""
        queryBuilder = SQLAQueryBuilder('Collection')
        response = self.app.get(url('/collections/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['searchParameters'] == h.getSearchParameters(queryBuilder)
