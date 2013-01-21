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
from old.model import ElicitationMethod
from old.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestElicitationMethodsController(TestController):

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
        """Tests that GET /elicitationmethods returns an array of all elicitation methods and that orderBy and pagination parameters work correctly."""

        # Add 100 elicitation methods.
        def createElicitationMethodFromIndex(index):
            elicitationMethod = model.ElicitationMethod()
            elicitationMethod.name = u'em%d' % index
            elicitationMethod.description = u'description %d' % index
            return elicitationMethod
        elicitationMethods = [createElicitationMethodFromIndex(i) for i in range(1, 101)]
        Session.add_all(elicitationMethods)
        Session.commit()
        elicitationMethods = h.getElicitationMethods(True)
        elicitationMethodsCount = len(elicitationMethods)

        # Test that GET /elicitationmethods gives us all of the elicitation methods.
        response = self.app.get(url('elicitationmethods'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == elicitationMethodsCount
        assert resp[0]['name'] == u'em1'
        assert resp[0]['id'] == elicitationMethods[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('elicitationmethods'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == elicitationMethods[46].name

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'ElicitationMethod', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('elicitationmethods'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted([em.name for em in elicitationMethods], reverse=True)
        assert resultSet == [em['name'] for em in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'ElicitationMethod', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('elicitationmethods'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['name']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'ElicitationMethod', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('elicitationmethods'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'ElicitationMethodist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('elicitationmethods'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == elicitationMethods[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('elicitationmethods'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('elicitationmethods'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

    #@nottest
    def test_create(self):
        """Tests that POST /elicitationmethods creates a new elicitation method
        or returns an appropriate error if the input is invalid.
        """

        originalEMCount = Session.query(ElicitationMethod).count()

        # Create a valid one
        params = json.dumps({'name': u'em', 'description': u'Described.'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newEMCount = Session.query(ElicitationMethod).count()
        assert newEMCount == originalEMCount + 1
        assert resp['name'] == u'em'
        assert resp['description'] == u'Described.'
        assert response.content_type == 'application/json'

        # Invalid because name is not unique
        params = json.dumps({'name': u'em', 'description': u'Described.'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'The submitted value for ElicitationMethod.name is not unique.'
        assert response.content_type == 'application/json'

        # Invalid because name is empty
        params = json.dumps({'name': u'', 'description': u'Described.'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'

        # Invalid because name is too long
        params = json.dumps({'name': u'name' * 400, 'description': u'Described.'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

    #@nottest
    def test_new(self):
        """Tests that GET /elicitationmethods/new returns an empty JSON object."""
        response = self.app.get(url('new_elicitationmethod'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /elicitationmethods/id updates the elicitationmethod with id=id."""

        # Create an elicitation method to update.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        elicitationMethodCount = Session.query(ElicitationMethod).count()
        elicitationMethodId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Update the elicitation method
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = json.dumps({'name': u'name', 'description': u'More content-ful description.'})
        response = self.app.put(url('elicitationmethod', id=elicitationMethodId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newElicitationMethodCount = Session.query(ElicitationMethod).count()
        assert elicitationMethodCount == newElicitationMethodCount
        assert datetimeModified != originalDatetimeModified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('elicitationmethod', id=elicitationMethodId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        elicitationMethodCount = newElicitationMethodCount
        newElicitationMethodCount = Session.query(ElicitationMethod).count()
        ourEMDatetimeModified = Session.query(ElicitationMethod).get(elicitationMethodId).datetimeModified
        assert ourEMDatetimeModified.isoformat() == datetimeModified
        assert elicitationMethodCount == newElicitationMethodCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /elicitationmethods/id deletes the elicitationMethod with id=id."""

        # Create an elicitation method to delete.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        elicitationMethodCount = Session.query(ElicitationMethod).count()
        elicitationMethodId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Now delete the elicitation method
        response = self.app.delete(url('elicitationmethod', id=elicitationMethodId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newElicitationMethodCount = Session.query(ElicitationMethod).count()
        assert newElicitationMethodCount == elicitationMethodCount - 1
        assert resp['id'] == elicitationMethodId
        assert response.content_type == 'application/json'

        # Trying to get the deleted elicitation method from the db should return None
        deletedElicitationMethod = Session.query(ElicitationMethod).get(elicitationMethodId)
        assert deletedElicitationMethod == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('elicitationmethod', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no elicitation method with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('elicitationmethod', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

    #@nottest
    def test_show(self):
        """Tests that GET /elicitationmethods/id returns the elicitation method with id=id or an appropriate error."""

        # Create an elicitation method to show.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        elicitationMethodCount = Session.query(ElicitationMethod).count()
        elicitationMethodId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Try to get a elicitationMethod using an invalid id
        id = 100000000000
        response = self.app.get(url('elicitationmethod', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no elicitation method with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('elicitationmethod', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

        # Valid id
        response = self.app.get(url('elicitationmethod', id=elicitationMethodId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'name'
        assert resp['description'] == u'description'
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /elicitationmethods/id/edit returns a JSON object of data necessary to edit the elicitation method with id=id.

        The JSON object is of the form {'elicitationMethod': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create an elicitation method to edit.
        params = json.dumps({'name': u'name', 'description': u'description'})
        response = self.app.post(url('elicitationmethods'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        elicitationMethodCount = Session.query(ElicitationMethod).count()
        elicitationMethodId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_elicitationmethod', id=elicitationMethodId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_elicitationmethod', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no elicitation method with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_elicitationmethod', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_elicitationmethod', id=elicitationMethodId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['elicitationMethod']['name'] == u'name'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'
