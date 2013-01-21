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
from old.model import Speaker
from old.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestSpeakersController(TestController):

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
        """Tests that GET /speakers returns an array of all speakers and that orderBy and pagination parameters work correctly."""

        # Add 100 speakers.
        def createSpeakerFromIndex(index):
            speaker = model.Speaker()
            speaker.firstName = u'John%d' % index
            speaker.lastName = u'Doe%d' % index
            speaker.dialect = u'dialect %d' % index
            speaker.pageContent = u'page content %d' % index
            return speaker
        speakers = [createSpeakerFromIndex(i) for i in range(1, 101)]
        Session.add_all(speakers)
        Session.commit()
        speakers = h.getSpeakers(True)
        speakersCount = len(speakers)

        # Test that GET /speakers gives us all of the speakers.
        response = self.app.get(url('speakers'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == speakersCount
        assert resp[0]['firstName'] == u'John1'
        assert resp[0]['id'] == speakers[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('speakers'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['firstName'] == speakers[46].firstName

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Speaker', 'orderByAttribute': 'firstName',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('speakers'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted([s.firstName for s in speakers], reverse=True)
        assert resultSet == [s['firstName'] for s in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Speaker', 'orderByAttribute': 'firstName',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('speakers'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['firstName']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Speaker', 'orderByAttribute': 'firstName',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('speakers'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Speakerist', 'orderByAttribute': 'prenom',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('speakers'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == speakers[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('speakers'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('speakers'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    #@nottest
    def test_create(self):
        """Tests that POST /speakers creates a new speaker
        or returns an appropriate error if the input is invalid.
        """

        originalSpeakerCount = Session.query(Speaker).count()

        # Create a valid one
        params = json.dumps({'firstName': u'John', 'lastName': u'Doe', 'pageContent': u'pageContent', 'dialect': u'dialect'})
        response = self.app.post(url('speakers'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newSpeakerCount = Session.query(Speaker).count()
        assert newSpeakerCount == originalSpeakerCount + 1
        assert resp['firstName'] == u'John'
        assert resp['dialect'] == u'dialect'
        assert response.content_type == 'application/json'

        # Invalid because firstName is too long
        params = json.dumps({'firstName': u'John' * 400, 'lastName': u'Doe', 'pageContent': u'pageContent', 'dialect': u'dialect'})
        response = self.app.post(url('speakers'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['firstName'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    #@nottest
    def test_new(self):
        """Tests that GET /speakers/new returns an empty JSON object."""
        response = self.app.get(url('new_speaker'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /speakers/id updates the speaker with id=id."""

        # Create a speaker to update.
        params = json.dumps({'firstName': u'firstName', 'lastName': u'lastName', 'pageContent': u'pageContent', 'dialect': u'dialect'})
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speakerCount = Session.query(Speaker).count()
        speakerId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Update the speaker
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = json.dumps({'firstName': u'firstName', 'lastName': u'lastName', 'pageContent': u'pageContent', 'dialect': u'updated dialect.'})
        response = self.app.put(url('speaker', id=speakerId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newSpeakerCount = Session.query(Speaker).count()
        assert speakerCount == newSpeakerCount
        assert datetimeModified != originalDatetimeModified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('speaker', id=speakerId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        speakerCount = newSpeakerCount
        newSpeakerCount = Session.query(Speaker).count()
        ourSpeakerDatetimeModified = Session.query(Speaker).get(speakerId).datetimeModified
        assert ourSpeakerDatetimeModified.isoformat() == datetimeModified
        assert speakerCount == newSpeakerCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /speakers/id deletes the speaker with id=id."""

        # Create a speaker to delete.
        params = json.dumps({'firstName': u'firstName', 'lastName': u'lastName', 'pageContent': u'pageContent', 'dialect': u'dialect'})
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speakerCount = Session.query(Speaker).count()
        speakerId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Now delete the speaker
        response = self.app.delete(url('speaker', id=speakerId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newSpeakerCount = Session.query(Speaker).count()
        assert newSpeakerCount == speakerCount - 1
        assert resp['id'] == speakerId
        assert response.content_type == 'application/json'

        # Trying to get the deleted speaker from the db should return None
        deletedSpeaker = Session.query(Speaker).get(speakerId)
        assert deletedSpeaker == None
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

    #@nottest
    def test_show(self):
        """Tests that GET /speakers/id returns the speaker with id=id or an appropriate error."""

        # Create a speaker to show.
        params = json.dumps({'firstName': u'firstName', 'lastName': u'lastName', 'pageContent': u'pageContent', 'dialect': u'dialect'})
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speakerCount = Session.query(Speaker).count()
        speakerId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

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
        response = self.app.get(url('speaker', id=speakerId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['firstName'] == u'firstName'
        assert resp['dialect'] == u'dialect'
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /speakers/id/edit returns a JSON object of data necessary to edit the speaker with id=id.

        The JSON object is of the form {'speaker': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a speaker to edit.
        params = json.dumps({'firstName': u'firstName', 'lastName': u'lastName', 'pageContent': u'pageContent', 'dialect': u'dialect'})
        response = self.app.post(url('speakers'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        speakerCount = Session.query(Speaker).count()
        speakerId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_speaker', id=speakerId), status=401)
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
        response = self.app.get(url('edit_speaker', id=speakerId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['speaker']['firstName'] == u'firstName'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'
