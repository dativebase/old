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
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Orthography
from onlinelinguisticdatabase.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestOrthographiesController(TestController):

    createParams = {
        'name': u'',
        'orthography': u'',
        'lowercase': False,
        'initialGlottalStops': True
    }

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

    @nottest
    def test_index(self):
        """Tests that GET /orthographies returns an array of all orthographies and that orderBy and pagination parameters work correctly."""

        # Add 100 orthographies.
        def createOrthographyFromIndex(index):
            orthography = model.Orthography()
            orthography.name = u'orthography%d' % index
            orthography.orthography = u'a, b, c, %d' % index
            orthography.initialGlottalStops = False
            orthography.lowercase = True
            return orthography
        orthographies = [createOrthographyFromIndex(i) for i in range(1, 101)]
        Session.add_all(orthographies)
        Session.commit()
        orthographies = h.getOrthographies(True)
        orthographiesCount = len(orthographies)

        # Test that GET /orthographies gives us all of the orthographies.
        response = self.app.get(url('orthographies'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == orthographiesCount
        assert resp[0]['name'] == u'orthography1'
        assert resp[0]['id'] == orthographies[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('orthographies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == orthographies[46].name
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Orthography', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('orthographies'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted([o.name for o in orthographies], reverse=True)
        assert resultSet == [o['name'] for o in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Orthography', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('orthographies'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['name']
        assert response.content_type == 'application/json'

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Orthography', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('orthographies'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Orthographyist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('orthographies'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == orthographies[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('orthographies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('orthographies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /orthographies creates a new orthography
        or returns an appropriate error if the input is invalid.
        """

        originalOrthographyCount = Session.query(Orthography).count()

        # Create a valid one
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newOrthographyCount = Session.query(Orthography).count()
        assert newOrthographyCount == originalOrthographyCount + 1
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initialGlottalStops'] == True    # default value from model/orthography.py
        assert response.content_type == 'application/json'

        # Invalid because name and orthography are empty
        params = self.createParams.copy()
        params.update({'name': u'', 'orthography': u''})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'
        assert resp['errors']['orthography'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name is too long
        params = self.createParams.copy()
        params.update({'name': u'orthography' * 200, 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

        # Boolean cols
        params = self.createParams.copy()
        params.update({
            'name': u'orthography',
            'orthography': u'a, b, c',
            'initialGlottalStops': False,
            'lowercase': True
        })
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthographyCount = newOrthographyCount
        newOrthographyCount = Session.query(Orthography).count()
        assert newOrthographyCount == orthographyCount + 1
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == True
        assert resp['initialGlottalStops'] == False

        # Boolean cols with string values.  Formencode.StringBoolean will convert
        # any non-zero numeral or float to True (otherwise False) and will convert
        # the following strings (with any case permutations) as indicated:
        # false_values = ['false', 'f', 'no', 'n', 'off', '0']
        # true_values = ['true', 't', 'yes', 'y', 'on', '1']
        # Any other string values will cause an Invalid error to be raised.
        params = self.createParams.copy()
        params.update({
            'name': u'orthography',
            'orthography': u'a, b, c',
            'initialGlottalStops': u'FALSE',
            'lowercase': u'truE'
        })
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthographyCount = newOrthographyCount
        newOrthographyCount = Session.query(Orthography).count()
        assert newOrthographyCount == orthographyCount + 1
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == True
        assert resp['initialGlottalStops'] == False

        params = self.createParams.copy()
        params.update({
            'name': u'orthography',
            'orthography': u'a, b, c',
            'initialGlottalStops': u'negative',
            'lowercase': u'althaea'
        })
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['lowercase'] == u"Value should be 'true' or 'false'"
        assert resp['errors']['initialGlottalStops'] == u"Value should be 'true' or 'false'"

    @nottest
    def test_new(self):
        """Tests that GET /orthographies/new returns an empty JSON object."""
        response = self.app.get(url('new_orthography'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /orthographies/id updates the orthography with id=id."""

        # Create an orthography to update.
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthographyCount = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initialGlottalStops'] == True    # default value from model/orthography.py
        assert response.content_type == 'application/json'
        orthographyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Update the orthography
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthographyId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newOrthographyCount = Session.query(Orthography).count()
        assert orthographyCount == newOrthographyCount
        assert datetimeModified != originalDatetimeModified
        assert resp['orthography'] == u'a, b, c, d'
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('orthography', id=orthographyId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        orthographyCount = newOrthographyCount
        newOrthographyCount = Session.query(Orthography).count()
        ourOrthographyDatetimeModified = Session.query(Orthography).get(orthographyId).datetimeModified
        assert ourOrthographyDatetimeModified.isoformat() == datetimeModified
        assert orthographyCount == newOrthographyCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Observe how updates are restricted when an orthography is part of an
        # active application settings ...
        appSet = h.generateDefaultApplicationSettings()
        appSet.storageOrthography = Session.query(Orthography).get(orthographyId)
        Session.add(appSet)
        Session.commit()

        # Now attempting a valid update as a contributor should fail
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d, e'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthographyId), params, self.json_headers,
                                 self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'Only administrators are permitted to update orthographies that are used in the active application settings.'
        assert response.content_type == 'application/json'

        # The same update as an admin should succeed.
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d, e'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthographyId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c, d, e'
        assert response.content_type == 'application/json'

        # If we now remove the orthography from the application settings, the
        # contributor will be able to edit it.
        appSet = h.getApplicationSettings()
        appSet.storageOrthography = None
        Session.commit()
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d, e, f'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthographyId), params, self.json_headers,
                                 self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c, d, e, f'

    @nottest
    def test_delete(self):
        """Tests that DELETE /orthographies/id deletes the orthography with id=id."""

        # Create an orthography to delete.
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthographyCount = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initialGlottalStops'] == True    # default value from model/orthography.py
        orthographyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Now delete the orthography
        response = self.app.delete(url('orthography', id=orthographyId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newOrthographyCount = Session.query(Orthography).count()
        assert newOrthographyCount == orthographyCount - 1
        assert resp['id'] == orthographyId
        assert response.content_type == 'application/json'

        # Trying to get the deleted orthography from the db should return None
        deletedOrthography = Session.query(Orthography).get(orthographyId)
        assert deletedOrthography == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('orthography', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no orthography with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('orthography', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Observe how deletions are restricted when an orthography is part of an
        # active application settings ...

        # Create an orthography to demonstrate.
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthographyCount = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initialGlottalStops'] == True    # default value from model/orthography.py
        orthographyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Create an application settings with the above orthography as the storage orthography
        appSet = h.generateDefaultApplicationSettings()
        appSet.storageOrthography = Session.query(Orthography).get(orthographyId)
        Session.add(appSet)
        Session.commit()

        # Now attempting to delete as a contributor should fail
        response = self.app.delete(url('orthography', id=orthographyId),
                    headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'Only administrators are permitted to delete orthographies that are used in the active application settings.'
        assert response.content_type == 'application/json'

        # If we now remove the orthography from the application settings, the
        # contributor will be able to delete it.
        appSet = h.getApplicationSettings()
        appSet.storageOrthography = None
        Session.commit()
        response = self.app.delete(url('orthography', id=orthographyId),
                    headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['orthography'] == u'a, b, c'

    @nottest
    def test_show(self):
        """Tests that GET /orthographies/id returns the orthography with id=id or an appropriate error."""

        # Create an orthography to show.
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthographyCount = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initialGlottalStops'] == True    # default value from model/orthography.py
        orthographyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Try to get an orthography using an invalid id
        id = 100000000000
        response = self.app.get(url('orthography', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no orthography with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('orthography', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('orthography', id=orthographyId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /orthographies/id/edit returns a JSON object of data necessary to edit the orthography with id=id.

        The JSON object is of the form {'orthography': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create an orthography to edit.
        params = self.createParams.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthographyCount = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initialGlottalStops'] == True    # default value from model/orthography.py
        orthographyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_orthography', id=orthographyId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_orthography', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no orthography with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_orthography', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_orthography', id=orthographyId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['orthography']['name'] == u'orthography'
        assert resp['orthography']['orthography'] == u'a, b, c'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'
