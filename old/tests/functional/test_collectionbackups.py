import datetime
import logging
import os
import webtest
import simplejson as json
from nose.tools import nottest
from base64 import encodestring
from paste.deploy import appconfig
from sqlalchemy.sql import desc
from uuid import uuid4
from old.tests import *
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h

log = logging.getLogger(__name__)


def addSEARCHToWebTestValidMethods():
    new_valid_methods = list(webtest.lint.valid_methods)
    new_valid_methods.append('SEARCH')
    new_valid_methods = tuple(new_valid_methods)
    webtest.lint.valid_methods = new_valid_methods

class TestCollectionbackupsController(TestController):

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

    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    def tearDown(self):
        # Clear all models in the database except Language; recreate the users.
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that GET & SEARCH /collectionbackups behave correctly.
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

        # Define some extra_environs
        view = {'test.authentication.role': u'viewer', 'test.applicationSettings': True}
        contrib = {'test.authentication.role': u'contributor', 'test.applicationSettings': True}
        admin = {'test.authentication.role': u'administrator', 'test.applicationSettings': True}

        params = self.createParams.copy()
        params.update({
            'title': u'Created by the Contributor',
            'elicitor': contributorId,
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('collections'), params, self.json_headers, contrib)
        collectionCount = Session.query(model.Collection).count()
        resp = json.loads(response.body)
        collectionId = resp['id']
        collectionUUID = resp['UUID']
        assert response.content_type == 'application/json'
        assert collectionCount == 1

        # Update our collection (via request) as the default administrator; this
        # will create one collection backup.
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
                        self.json_headers, admin)
        resp = json.loads(response.body)
        collectionCount = Session.query(model.Collection).count()
        assert response.content_type == 'application/json'
        assert collectionCount == 1

        # Finally, update our collection (via request) as the default contributor.
        # Now we will have two collection backups.
        params = self.createParams.copy()
        params.update({
            'title': u'Updated by the Contributor',
            'speaker': speakerId,
            'tags': tagIds,
            'files': fileIds
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collectionId), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        collectionCount = Session.query(model.Collection).count()
        assert collectionCount == 1

        # Now GET the collection backups as the restricted enterer of the original
        # collection and expect to get them all.
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=contrib)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert response.content_type == 'application/json'

        # The admin should get them all too.
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # The viewer should get none because they're all restricted.
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        assert len(resp) == 0

        # Now update the collection and de-restrict it.
        params = self.createParams.copy()
        params.update({
            'title': u'Updated and de-restricted by the Contributor',
            'speaker': speakerId,
            'tags': [],
            'files': fileIds
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collectionId), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        collectionCount = Session.query(model.Collection).count()
        assert collectionCount == 1

        # Now GET the collection backups.  Admin and contrib should see 3 but the
        # viewer should still see none.
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=contrib)
        resp = json.loads(response.body)
        assert len(resp) == 3
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp) == 3
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        assert len(resp) == 0
        assert response.content_type == 'application/json'

        # Finally, update our collection in some trivial way.
        params = self.createParams.copy()
        params.update({
            'title': u'Updated by the Contributor *again*',
            'speaker': speakerId,
            'tags': [],
            'files': fileIds
        })
        params = json.dumps(params)
        response = self.app.put(url('collection', id=collectionId), params,
                        self.json_headers, contrib)
        resp = json.loads(response.body)
        collectionCount = Session.query(model.Collection).count()
        assert collectionCount == 1

        # Now GET the collection backups.  Admin and contrib should see 4 and the
        # viewer should see 1
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=contrib)
        resp = json.loads(response.body)
        assert len(resp) == 4
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        allCollectionBackups = resp
        assert len(resp) == 4
        response = self.app.get(url('collectionbackups'), headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        unrestrictedCollectionBackup = resp[0]
        assert len(resp) == 1
        assert resp[0]['title'] == u'Updated and de-restricted by the Contributor'
        restrictedCollectionBackups = [cb for cb in allCollectionBackups
                                       if cb != unrestrictedCollectionBackup]
        assert len(restrictedCollectionBackups) == 3

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 1, 'page': 2}
        response = self.app.get(url('collectionbackups'), paginator, headers=self.json_headers,
                                extra_environ=admin)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['title'] == allCollectionBackups[1]['title']
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'CollectionBackup', 'orderByAttribute': 'datetimeModified',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('collectionbackups'), orderByParams,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        resultSet = sorted(allCollectionBackups, key=lambda cb: cb['datetimeModified'], reverse=True)
        assert [cb['id'] for cb in resp] == [cb['id'] for cb in resultSet]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'CollectionBackup', 'orderByAttribute': 'datetimeModified',
                     'orderByDirection': 'desc', 'itemsPerPage': 1, 'page': 3}
        response = self.app.get(url('collectionbackups'), params,
                        headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert resultSet[2]['title'] == resp['items'][0]['title']

        # Now test the show action:

        # Admin should be able to GET a particular restricted collection backup
        response = self.app.get(url('collectionbackup', id=restrictedCollectionBackups[0]['id']),
                                headers=self.json_headers, extra_environ=admin)
        resp = json.loads(response.body)
        assert resp['title'] == restrictedCollectionBackups[0]['title']
        assert response.content_type == 'application/json'

        # Viewer should receive a 403 error when attempting to do so.
        response = self.app.get(url('collectionbackup', id=restrictedCollectionBackups[0]['id']),
                                headers=self.json_headers, extra_environ=view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Viewer should be able to GET the unrestricted collection backup
        response = self.app.get(url('collectionbackup', id=unrestrictedCollectionBackup['id']),
                                headers=self.json_headers, extra_environ=view)
        resp = json.loads(response.body)
        assert resp['title'] == unrestrictedCollectionBackup['title']

        # A nonexistent cb id will return a 404 error
        response = self.app.get(url('collectionbackup', id=100987),
                    headers=self.json_headers, extra_environ=view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no collection backup with id 100987'
        assert response.content_type == 'application/json'

        # Test the search action
        addSEARCHToWebTestValidMethods()

        # A search on collection backup titles using POST /collectionbackups/search
        jsonQuery = json.dumps({'query': {'filter':
                        ['CollectionBackup', 'title', 'like', u'%Contributor%']}})
        response = self.app.post(url('/collectionbackups/search'), jsonQuery,
                        self.json_headers, admin)
        resp = json.loads(response.body)
        resultSet = [cb for cb in allCollectionBackups if u'Contributor' in cb['title']]
        assert len(resp) == len(resultSet) == 3
        assert set([cb['id'] for cb in resp]) == set([cb['id'] for cb in resultSet])
        assert response.content_type == 'application/json'

        # A search on collection backup titles using SEARCH /collectionbackups
        jsonQuery = json.dumps({'query': {'filter':
                        ['CollectionBackup', 'title', 'like', u'%Administrator%']}})
        response = self.app.request(url('collectionbackups'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=admin)
        resp = json.loads(response.body)
        resultSet = [cb for cb in allCollectionBackups if u'Administrator' in cb['title']]
        assert len(resp) == len(resultSet) == 1
        assert set([cb['id'] for cb in resp]) == set([cb['id'] for cb in resultSet])

        # Perform the two previous searches as a restricted viewer to show that
        # the restricted tag is working correctly.
        jsonQuery = json.dumps({'query': {'filter':
                        ['CollectionBackup', 'title', 'like', u'%Contributor%']}})
        response = self.app.post(url('/collectionbackups/search'), jsonQuery,
                        self.json_headers, view)
        resp = json.loads(response.body)
        resultSet = [cb for cb in [unrestrictedCollectionBackup]
                     if u'Contributor' in cb['title']]
        assert len(resp) == len(resultSet) == 1
        assert set([cb['id'] for cb in resp]) == set([cb['id'] for cb in resultSet])

        jsonQuery = json.dumps({'query': {'filter':
                        ['CollectionBackup', 'title', 'like', u'%Administrator%']}})
        response = self.app.request(url('collectionbackups'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=view)
        resp = json.loads(response.body)
        resultSet = [cb for cb in [unrestrictedCollectionBackup]
                     if u'Administrator' in cb['title']]
        assert len(resp) == len(resultSet) == 0

        # I'm just going to assume that the order by and pagination functions are
        # working correctly since the implementation is essentially equivalent
        # to that in the index action already tested above.

        # Attempting to call edit/new/create/delete/update on a read-only resource
        # will return a 404 response
        response = self.app.get(url('edit_collectionbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.get(url('new_collectionbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.post(url('collectionbackups'), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.put(url('collectionbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        response = self.app.delete(url('collectionbackup', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'
