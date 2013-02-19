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
import simplejson as json
from time import sleep
from nose.tools import nottest
from paste.deploy import appconfig
from sqlalchemy.sql import desc
import webtest
from old.tests import *
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h
from old.model import Tag
from old.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestTagsController(TestController):

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language; recreate the users.
    def tearDown(self):
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that GET /tags returns an array of all tags and that orderBy and pagination parameters work correctly."""

        # Add 100 tags.
        def createTagFromIndex(index):
            tag = model.Tag()
            tag.name = u'tag%d' % index
            tag.description = u'description %d' % index
            return tag
        tags = [createTagFromIndex(i) for i in range(1, 101)]
        Session.add_all(tags)
        Session.commit()
        tags = h.getTags(True)
        tagsCount = len(tags)

        # Test that GET /tags gives us all of the tags.
        response = self.app.get(url('tags'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == tagsCount
        assert resp[0]['name'] == u'tag1'
        assert resp[0]['id'] == tags[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('tags'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == tags[46].name
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Tag', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('tags'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted([t.name for t in tags], reverse=True)
        assert resultSet == [t['name'] for t in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Tag', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('tags'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['name']
        assert response.content_type == 'application/json'

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Tag', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('tags'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Tagist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('tags'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == tags[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('tags'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('tags'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    #@nottest
    def test_create(self):
        """Tests that POST /tags creates a new tag
        or returns an appropriate error if the input is invalid.
        """

        originalTagCount = Session.query(Tag).count()

        # Create a valid one
        params = json.dumps({'name': u'tag', 'description': u'Described.'})
        response = self.app.post(url('tags'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newTagCount = Session.query(Tag).count()
        assert newTagCount == originalTagCount + 1
        assert resp['name'] == u'tag'
        assert resp['description'] == u'Described.'
        assert response.content_type == 'application/json'

        # Invalid because name is not unique
        params = json.dumps({'name': u'tag', 'description': u'Described.'})
        response = self.app.post(url('tags'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'The submitted value for Tag.name is not unique.'

        # Invalid because name is empty
        params = json.dumps({'name': u'', 'description': u'Described.'})
        response = self.app.post(url('tags'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name is too long
        params = json.dumps({'name': u'name' * 400, 'description': u'Described.'})
        response = self.app.post(url('tags'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    #@nottest
    def test_new(self):
        """Tests that GET /tags/new returns an empty JSON object."""
        response = self.app.get(url('new_tag'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /tags/id updates the tag with id=id."""

        # Create a tag to update.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('tags'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        tagCount = Session.query(Tag).count()
        tagId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Update the tag
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = json.dumps({'name': u'name', 'description': u'More content-ful description.'})
        response = self.app.put(url('tag', id=tagId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newTagCount = Session.query(Tag).count()
        assert tagCount == newTagCount
        assert datetimeModified != originalDatetimeModified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('tag', id=tagId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        tagCount = newTagCount
        newTagCount = Session.query(Tag).count()
        ourTagDatetimeModified = Session.query(Tag).get(tagId).datetimeModified
        assert ourTagDatetimeModified.isoformat() == datetimeModified
        assert tagCount == newTagCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /tags/id deletes the tag with id=id."""

        # Create a tag to delete.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('tags'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        tagCount = Session.query(Tag).count()
        tagId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Now delete the tag
        response = self.app.delete(url('tag', id=tagId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newTagCount = Session.query(Tag).count()
        assert newTagCount == tagCount - 1
        assert resp['id'] == tagId
        assert response.content_type == 'application/json'

        # Trying to get the deleted tag from the db should return None
        deletedTag = Session.query(Tag).get(tagId)
        assert deletedTag == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('tag', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no tag with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('tag', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Create a form, tag it, delete the tag and show that the form no longer
        # has the tag.
        tag = model.Tag()
        tag.name = u'tag'
        form = model.Form()
        form.transcription = u'test'
        form.tags.append(tag)
        Session.add_all([form, tag])
        Session.commit()
        formId = form.id
        tagId = tag.id
        response = self.app.delete(url('tag', id=tagId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        deletedTag = Session.query(Tag).get(tagId)
        form = Session.query(model.Form).get(formId)
        assert response.content_type == 'application/json'
        assert deletedTag == None
        assert form.tags == []

    #@nottest
    def test_show(self):
        """Tests that GET /tags/id returns the tag with id=id or an appropriate error."""

        # Create a tag to show.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('tags'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        tagCount = Session.query(Tag).count()
        tagId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Try to get a tag using an invalid id
        id = 100000000000
        response = self.app.get(url('tag', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no tag with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('tag', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('tag', id=tagId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'name'
        assert resp['description'] == u'description'
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /tags/id/edit returns a JSON object of data necessary to edit the tag with id=id.

        The JSON object is of the form {'tag': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a tag to edit.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('tags'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        tagCount = Session.query(Tag).count()
        tagId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_tag', id=tagId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_tag', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no tag with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_tag', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_tag', id=tagId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['tag']['name'] == u'name'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'
