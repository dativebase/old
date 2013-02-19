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
from old.tests import *
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h
from old.model import Phonology
from old.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


class TestPhonologiesController(TestController):

    here = appconfig('config:test.ini', relative_to='.')['here']
    researchersPath = os.path.join(here, 'files', 'researchers')

    createParams = {
        'name': u'',
        'description': u'',
        'script': u''
    }

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language; recreate the phonologies.
    def tearDown(self):
        h.clearAllModels()
        h.destroyAllResearcherDirectories()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that GET /phonologies returns an array of all phonologies and that orderBy and pagination parameters work correctly."""

        # Add 100 phonologies.
        def createPhonologyFromIndex(index):
            phonology = model.Phonology()
            phonology.name = u'Phonology %d' % index
            phonology.description = u'A phonology with %d rules' % index
            phonology.script = u'# After this comment, the script will begin.\n\n'
            return phonology
        phonologies = [createPhonologyFromIndex(i) for i in range(1, 101)]
        Session.add_all(phonologies)
        Session.commit()
        phonologies = h.getPhonologies(True)
        phonologiesCount = len(phonologies)

        # Test that GET /phonologies gives us all of the phonologies.
        response = self.app.get(url('phonologies'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == phonologiesCount
        assert resp[0]['name'] == u'Phonology 1'
        assert resp[0]['id'] == phonologies[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == phonologies[46].name
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Phonology', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('phonologies'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted(phonologies, key=lambda p: p.name, reverse=True)
        assert [p.id for p in resultSet] == [p['id'] for p in resp]
        assert response.content_type == 'application/json'

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Phonology', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('phonologies'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46].name == resp['items'][0]['name']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Phonology', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('phonologies'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Phonologyist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('phonologies'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == phonologies[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    #@nottest
    def test_create(self):
        """Tests that POST /phonologies creates a new phonology
        or returns an appropriate error if the input is invalid.
        """

        # Attempt to create a phonology as a viewer and expect to fail
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Create a valid one
        originalPhonologyCount = Session.query(Phonology).count()
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert response.content_type == 'application/json'

        # Invalid because name is not unique
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'The submitted value for Phonology.name is not unique.'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.createParams.copy()
        params.update({
            'name': u'',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.createParams.copy()
        params.update({
            'name': None,
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name is too long.
        params = self.createParams.copy()
        params.update({
            'name': 'Phonology' * 200,
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    #@nottest
    def test_new(self):
        """Tests that GET /phonologies/new returns an empty JSON object."""
        response = self.app.get(url('new_phonology'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /phonologies/id updates the phonology with id=id."""

        # Create a phonology to update.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Update the phonology
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.  Best yet!',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonologyId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newPhonologyCount = Session.query(Phonology).count()
        assert phonologyCount == newPhonologyCount
        assert datetimeModified != originalDatetimeModified
        assert resp['description'] == u'Covers a lot of the data.  Best yet!'
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('phonology', id=phonologyId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        ourPhonologyDatetimeModified = Session.query(Phonology).get(phonologyId).datetimeModified
        assert ourPhonologyDatetimeModified.isoformat() == datetimeModified
        assert phonologyCount == newPhonologyCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /phonologies/id deletes the phonology with id=id."""

        # Create a phonology to delete.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Now delete the phonology
        response = self.app.delete(url('phonology', id=phonologyId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount - 1
        assert resp['id'] == phonologyId
        assert response.content_type == 'application/json'

        # Trying to get the deleted phonology from the db should return None
        deletedPhonology = Session.query(Phonology).get(phonologyId)
        assert deletedPhonology == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('phonology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no phonology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('phonology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_show(self):
        """Tests that GET /phonologies/id returns the phonology with id=id or an appropriate error."""

        # Create a phonology to show.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Try to get a phonology using an invalid id
        id = 100000000000
        response = self.app.get(url('phonology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no phonology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('phonology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('phonology', id=phonologyId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert resp['script'] == u'# The rules will begin after this comment.\n\n'
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /phonologies/id/edit returns a JSON object of data necessary to edit the phonology with id=id.

        The JSON object is of the form {'phonology': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a phonology to edit.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_phonology', id=phonologyId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_phonology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no phonology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_phonology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_phonology', id=phonologyId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['phonology']['name'] == u'Phonology'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'
