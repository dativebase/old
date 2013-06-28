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

import logging
import simplejson as json
from time import sleep
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Orthography

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestOrthographiesController(TestController):

    @nottest
    def test_index(self):
        """Tests that GET /orthographies returns an array of all orthographies and that order_by and pagination parameters work correctly."""

        # Add 100 orthographies.
        def create_orthography_from_index(index):
            orthography = model.Orthography()
            orthography.name = u'orthography%d' % index
            orthography.orthography = u'a, b, c, %d' % index
            orthography.initial_glottal_stops = False
            orthography.lowercase = True
            return orthography
        orthographies = [create_orthography_from_index(i) for i in range(1, 101)]
        Session.add_all(orthographies)
        Session.commit()
        orthographies = h.get_orthographies(True)
        orthographies_count = len(orthographies)

        # Test that GET /orthographies gives us all of the orthographies.
        response = self.app.get(url('orthographies'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == orthographies_count
        assert resp[0]['name'] == u'orthography1'
        assert resp[0]['id'] == orthographies[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'items_per_page': 23, 'page': 3}
        response = self.app.get(url('orthographies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == orthographies[46].name
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'Orthography', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('orthographies'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        result_set = sorted([o.name for o in orthographies], reverse=True)
        assert result_set == [o['name'] for o in resp]

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'Orthography', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc', 'items_per_page': 23, 'page': 3}
        response = self.app.get(url('orthographies'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert result_set[46] == resp['items'][0]['name']
        assert response.content_type == 'application/json'

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'Orthography', 'order_by_attribute': 'name',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('orthographies'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the order_by_model/Attribute
        # param is invalid.
        order_by_params = {'order_by_model': 'Orthographyist', 'order_by_attribute': 'nominal',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('orthographies'), order_by_params,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == orthographies[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'items_per_page': u'a', 'page': u''}
        response = self.app.get(url('orthographies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'items_per_page': 0, 'page': -1}
        response = self.app.get(url('orthographies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /orthographies creates a new orthography
        or returns an appropriate error if the input is invalid.
        """

        original_orthography_count = Session.query(Orthography).count()

        # Create a valid one
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography 1', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_orthography_count = Session.query(Orthography).count()
        assert new_orthography_count == original_orthography_count + 1
        assert resp['name'] == u'orthography 1'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initial_glottal_stops'] == True    # default value from model/orthography.py
        assert response.content_type == 'application/json'

        # Invalid because name and orthography are empty
        params = self.orthography_create_params.copy()
        params.update({'name': u'', 'orthography': u''})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'
        assert resp['errors']['orthography'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name is too long
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography' * 200, 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

        # Boolean cols
        params = self.orthography_create_params.copy()
        params.update({
            'name': u'orthography 2',
            'orthography': u'a, b, c',
            'initial_glottal_stops': False,
            'lowercase': True
        })
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthography_count = new_orthography_count
        new_orthography_count = Session.query(Orthography).count()
        assert new_orthography_count == orthography_count + 1
        assert resp['name'] == u'orthography 2'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == True
        assert resp['initial_glottal_stops'] == False

        # Boolean cols with string values.  Formencode.StringBoolean will convert
        # any non-zero numeral or float to True (otherwise False) and will convert
        # the following strings (with any case permutations) as indicated:
        # false_values = ['false', 'f', 'no', 'n', 'off', '0']
        # true_values = ['true', 't', 'yes', 'y', 'on', '1']
        # Any other string values will cause an Invalid error to be raised.
        params = self.orthography_create_params.copy()
        params.update({
            'name': u'orthography 3',
            'orthography': u'a, b, c',
            'initial_glottal_stops': u'FALSE',
            'lowercase': u'truE'
        })
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthography_count = new_orthography_count
        new_orthography_count = Session.query(Orthography).count()
        assert new_orthography_count == orthography_count + 1
        assert resp['name'] == u'orthography 3'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == True
        assert resp['initial_glottal_stops'] == False

        params = self.orthography_create_params.copy()
        params.update({
            'name': u'orthography 4',
            'orthography': u'a, b, c',
            'initial_glottal_stops': u'negative',
            'lowercase': u'althaea'
        })
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['lowercase'] == u"Value should be 'true' or 'false'"
        assert resp['errors']['initial_glottal_stops'] == u"Value should be 'true' or 'false'"

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
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthography_count = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initial_glottal_stops'] == True    # default value from model/orthography.py
        assert response.content_type == 'application/json'
        orthography_id = resp['id']
        original_datetime_modified = resp['datetime_modified']

        # Update the orthography
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetime_modified for the update
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthography_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetime_modified = resp['datetime_modified']
        new_orthography_count = Session.query(Orthography).count()
        assert orthography_count == new_orthography_count
        assert datetime_modified != original_datetime_modified
        assert resp['orthography'] == u'a, b, c, d'
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        response = self.app.put(url('orthography', id=orthography_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        orthography_count = new_orthography_count
        new_orthography_count = Session.query(Orthography).count()
        our_orthography_datetime_modified = Session.query(Orthography).get(orthography_id).datetime_modified
        assert our_orthography_datetime_modified.isoformat() == datetime_modified
        assert orthography_count == new_orthography_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Observe how updates are restricted when an orthography is part of an
        # active application settings ...
        app_set = h.generate_default_application_settings()
        app_set.storage_orthography = Session.query(Orthography).get(orthography_id)
        Session.add(app_set)
        Session.commit()

        # Now attempting a valid update as a contributor should fail
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d, e'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthography_id), params, self.json_headers,
                                 self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'Only administrators are permitted to update orthographies that are used in the active application settings.'
        assert response.content_type == 'application/json'

        # The same update as an admin should succeed.
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d, e'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthography_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c, d, e'
        assert response.content_type == 'application/json'

        # If we now remove the orthography from the application settings, the
        # contributor will be able to edit it.
        app_set = h.get_application_settings()
        app_set.storage_orthography = None
        Session.commit()
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c, d, e, f'})
        params = json.dumps(params)
        response = self.app.put(url('orthography', id=orthography_id), params, self.json_headers,
                                 self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c, d, e, f'

    @nottest
    def test_delete(self):
        """Tests that DELETE /orthographies/id deletes the orthography with id=id."""

        # Create an orthography to delete.
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthography_count = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initial_glottal_stops'] == True    # default value from model/orthography.py
        orthography_id = resp['id']
        original_datetime_modified = resp['datetime_modified']

        # Now delete the orthography
        response = self.app.delete(url('orthography', id=orthography_id), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        new_orthography_count = Session.query(Orthography).count()
        assert new_orthography_count == orthography_count - 1
        assert resp['id'] == orthography_id
        assert response.content_type == 'application/json'

        # Trying to get the deleted orthography from the db should return None
        deleted_orthography = Session.query(Orthography).get(orthography_id)
        assert deleted_orthography == None

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
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        orthography_count = Session.query(Orthography).count()
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initial_glottal_stops'] == True    # default value from model/orthography.py
        orthography_id = resp['id']

        # Create an application settings with the above orthography as the storage orthography
        app_set = h.generate_default_application_settings()
        app_set.storage_orthography = Session.query(Orthography).get(orthography_id)
        Session.add(app_set)
        Session.commit()

        # Now attempting to delete as a contributor should fail
        response = self.app.delete(url('orthography', id=orthography_id),
                    headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'Only administrators are permitted to delete orthographies that are used in the active application settings.'
        assert response.content_type == 'application/json'

        # If we now remove the orthography from the application settings, the
        # contributor will be able to delete it.
        app_set = h.get_application_settings()
        app_set.storage_orthography = None
        Session.commit()
        response = self.app.delete(url('orthography', id=orthography_id),
                    headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['orthography'] == u'a, b, c'

    @nottest
    def test_show(self):
        """Tests that GET /orthographies/id returns the orthography with id=id or an appropriate error."""

        # Create an orthography to show.
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initial_glottal_stops'] == True    # default value from model/orthography.py
        orthography_id = resp['id']

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
        response = self.app.get(url('orthography', id=orthography_id), headers=self.json_headers,
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
        params = self.orthography_create_params.copy()
        params.update({'name': u'orthography', 'orthography': u'a, b, c'})
        params = json.dumps(params)
        response = self.app.post(url('orthographies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'orthography'
        assert resp['orthography'] == u'a, b, c'
        assert resp['lowercase'] == False   # default value from model/orthography.py
        assert resp['initial_glottal_stops'] == True    # default value from model/orthography.py
        orthography_id = resp['id']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_orthography', id=orthography_id), status=401)
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
        response = self.app.get(url('edit_orthography', id=orthography_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['orthography']['name'] == u'orthography'
        assert resp['orthography']['orthography'] == u'a, b, c'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'
