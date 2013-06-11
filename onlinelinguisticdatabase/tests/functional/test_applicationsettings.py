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
import simplejson as json
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
from onlinelinguisticdatabase.model import ApplicationSettings, User, Orthography
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h

log = logging.getLogger(__name__)

def add_default_application_settings():
    """Add the default application settings to the database."""
    orthography1 = h.generate_default_orthography1()
    orthography2 = h.generate_default_orthography2()
    contributor = Session.query(User).filter(User.role==u'contributor').first()
    application_settings = h.generate_default_application_settings([orthography1, orthography2], [contributor])
    Session.add(application_settings)
    Session.commit()
    return application_settings


class TestApplicationsettingsController(TestController):

    @nottest
    def test_index(self):
        """Tests that GET /applicationsettings returns a JSON array of application settings objects."""
        # Add the default application settings.
        application_settings = add_default_application_settings()
        response = self.app.get(url('applicationsettings'),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['object_language_name'] == application_settings.object_language_name
        assert resp[0]['storage_orthography']['name'] == application_settings.storage_orthography.name
        assert resp[0]['unrestricted_users'][0]['role'] == application_settings.unrestricted_users[0].role

    @nottest
    def test_create(self):
        """Tests that POST /applicationsettings correctly creates a new application settings."""

        # Add some orthographies.
        orthography1 = h.generate_default_orthography1()
        orthography2 = h.generate_default_orthography2()
        Session.add_all([orthography1, orthography2])
        Session.commit()
        orthography2_id = orthography2.id
        orthography2_orthography = orthography2.orthography

        params = self.application_settings_create_params.copy()
        params.update({
            'object_language_name': u'test_create object language name',
            'object_language_id': u'tco',
            'metalanguage_name': u'test_create metalanguage name',
            'metalanguage_id': u'tcm',
            'orthographic_validation': u'Warning',
            'narrow_phonetic_validation': u'Error',
            'morpheme_break_is_orthographic': False,
            'morpheme_delimiters': u'-,+',
            'punctuation': u'!?.,;:-_',
            'grammaticalities': u'*,**,***,?,??,???,#,##,###',
            'unrestricted_users': [Session.query(User).filter(
                User.role==u'viewer').first().id],
            'storage_orthography': orthography2_id,
            'input_orthography': orthography2_id,
            'output_orthography': orthography2_id
        })
        params = json.dumps(params)

        response = self.app.post(url('applicationsettings'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['object_language_name'] == u'test_create object language name'
        assert resp['morpheme_break_is_orthographic'] is False
        assert resp['storage_orthography']['orthography'] == orthography2_orthography
        assert resp['unrestricted_users'][0]['first_name'] == u'Viewer'
        assert 'password' not in resp['unrestricted_users'][0]
        assert response.content_type == 'application/json'

        # Attempt the same above creation as a contributor and expect to fail.
        response = self.app.post(url('applicationsettings'), params,
            self.json_headers, self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

    @nottest
    def test_create_invalid(self):
        """Tests that POST /applicationsettings responds with an appropriate error when invalid params are submitted in the request."""

        params = self.application_settings_create_params.copy()
        params.update({
            'object_language_name': u'!' * 256,   # too long
            'object_language_id': u'too long',    # too long also
            'orthographic_validation': u'No Way!', # not a valid value
            # formencode.validators.StringBoolean accepts 'true', 'false' (with
            # any character in uppercase) as well as any int or float.  'Truish'
            # is unacceptable.
            'morpheme_break_is_orthographic': u'Truish',
            'storage_orthography': 'accept me!'  # integer (orth.id) required
        })
        params = json.dumps(params)
        response = self.app.post(url('applicationsettings'), params,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['errors']['object_language_id'] == \
            u'Enter a value not more than 3 characters long'
        assert resp['errors']['object_language_name'] == \
            u'Enter a value not more than 255 characters long'
        assert u'Value must be one of: None; Warning; Error' in \
            resp['errors']['orthographic_validation']
        assert u"Value should be 'true' or 'false'" in \
            resp['errors']['morpheme_break_is_orthographic']
        assert resp['errors']['storage_orthography'] == \
            u'Please enter an integer value'

    @nottest
    def test_new(self):
        """Tests that GET /applicationsettings/new returns an appropriate JSON object for creating a new application settings object.

        The properties of the JSON object are 'languages', 'users' and
        'orthographies' and their values are arrays/lists.
        """

        # Add some orthographies.
        orthography1 = h.generate_default_orthography1()
        orthography2 = h.generate_default_orthography2()
        Session.add_all([orthography1, orthography2])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'languages': h.get_languages(),
            'users': h.get_mini_dicts_getter('User')(),
            'orthographies': h.get_mini_dicts_getter('Orthography')()
        }

        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # GET /applicationsettings/new without params.  Expect a JSON array for
        # every store.
        response = self.app.get(url('new_applicationsetting'),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['languages'] == data['languages']
        assert resp['users'] == data['users']
        assert resp['orthographies'] == data['orthographies']
        assert response.content_type == 'application/json'

        # GET /applicationsettings/new with params.  Param values are treated as
        # strings, not JSON.  If any params are specified, the default is to
        # return a JSON array corresponding to store for the param.  There are
        # three cases that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetime_modified value of the
        #    store in question.
        params = {
            # Value is empty string: 'languages' will not be in response.
            'languages': '',
            # Value is any string: 'users' will be in response.
            'users': 'anything can go here!',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Orthography.datetime_modified value: 'orthographies' *will*
            # be in the response.
            'orthographies': datetime.datetime.utcnow().isoformat(),
        }
        response = self.app.get(url('new_applicationsetting'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['languages'] == []
        assert resp['users'] == data['users']
        assert resp['orthographies'] == data['orthographies']

    @nottest
    def test_update(self):
        """Tests that PUT /applicationsettings/id correctly updates an existing application settings."""

        application_settings_count = Session.query(
            ApplicationSettings).count()
        contributor_id = Session.query(User).filter(User.role==u'contributor').first().id

        # Create an application settings to update.
        params = self.application_settings_create_params.copy()
        params.update({
            'object_language_name': u'test_update object language name',
            'object_language_id': u'tuo',
            'metalanguage_name': u'test_update metalanguage name',
            'metalanguage_id': u'tum',
            'orthographic_validation': u'None',
            'narrow_phonetic_validation': u'Warning',
            'morpheme_break_is_orthographic': True,
            'morpheme_delimiters': u'+',
            'punctuation': u'!.;:',
            'grammaticalities': u'*,**,?,??,#,##',
            'unrestricted_users': [contributor_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('applicationsettings'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        id = int(resp['id'])
        new_application_settings_count = Session.query(ApplicationSettings).count()
        assert resp['object_language_name'] == u'test_update object language name'
        assert resp['unrestricted_users'][0]['role'] == u'contributor'
        assert new_application_settings_count == application_settings_count + 1

        # Update the application settings we just created but expect to fail
        # because the unrestricted users ids are invalid.
        params = self.application_settings_create_params.copy()
        params.update({
            'object_language_name': u'Updated!',
            'unrestricted_users': [2000, 5000],
            'morpheme_delimiters': u'-,='
        })
        params = json.dumps(params)
        response = self.app.put(url('applicationsetting', id=id), params,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        application_settings_count = new_application_settings_count
        new_application_settings_count = Session.query(ApplicationSettings).count()
        assert resp['errors']['unrestricted_users'] == [u"There is no user with id 2000.", u"There is no user with id 5000."]
        assert new_application_settings_count == application_settings_count
        assert response.content_type == 'application/json'

        # Update the application settings.
        params = self.application_settings_create_params.copy()
        params.update({
            'object_language_name': u'Updated!',
            'unrestricted_users': [contributor_id],
            'morpheme_delimiters': u'-,='
        })
        params = json.dumps(params)
        response = self.app.put(url('applicationsetting', id=id), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        application_settings_count = new_application_settings_count
        new_application_settings_count = Session.query(ApplicationSettings).count()
        assert resp['object_language_name'] == u'Updated!'
        assert new_application_settings_count == application_settings_count
        assert response.content_type == 'application/json'

        # Attempt an update with no new data -- expect a 400 status code where
        # the response body is a JSON object with an appropriate 'error'
        # attribute.
        response = self.app.put(url('applicationsetting', id=id), params,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'the submitted data were not new' in resp['error']

        # Unauthorized update attempt as contributor
        params = self.application_settings_create_params.copy()
        params.update({
            'object_language_name': u'Updated by a contrib!',
            'unrestricted_users': [contributor_id],
            'morpheme_delimiters': u'-,='
        })
        params = json.dumps(params)
        response = self.app.put(url('applicationsetting', id=id), params,
                        self.json_headers, self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

    @nottest
    def test_delete(self):
        """Tests that DELETE /applicationsettings/id deletes the application settings with id=id and returns a JSON representation.

        If the id is invalid or unspecified, then JSON null or a 404 status code
        are returned, respectively.
        """

        # Count the original number of application settings.
        application_settings_count = Session.query(
            ApplicationSettings).count()

        # Add an orthography.
        orthography1 = h.generate_default_orthography1()
        Session.add(orthography1)
        Session.commit()
        orthography1 = h.get_orthographies()[0]
        orthography1_id = orthography1.id
        orthography1 = Session.query(Orthography).get(orthography1_id)

        # First create an application settings to delete.
        params = self.application_settings_create_params.copy()
        params.update({
            'object_language_name': u'test_delete object language name',
            'object_language_id': u'tdo',
            'metalanguage_name': u'test_delete metalanguage name',
            'metalanguage_id': u'tdm',
            'storage_orthography': orthography1_id,
            'morpheme_delimiters': u'-'
        })
        params = json.dumps(params)
        response = self.app.post(url('applicationsettings'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_application_settings_count = Session.query(
            ApplicationSettings).count()
        assert resp['object_language_name'] == u'test_delete object language name'
        assert new_application_settings_count == application_settings_count + 1

        # Delete the application settings we just created
        response = self.app.delete(
            url('applicationsetting', id=resp['id']),
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        new_application_settings_count = Session.query(ApplicationSettings).count()
        assert new_application_settings_count == application_settings_count
        assert response.content_type == 'application/json'
        # The deleted application settings will be returned to us, so the
        # assertions from above should still hold true.
        assert resp['object_language_name'] == u'test_delete object language name'

        # Trying to get the deleted form from the db should return None.
        deleted_application_settings = Session.query(
            ApplicationSettings).get(resp['id'])
        assert deleted_application_settings == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('applicationsetting', id=id),
                            extra_environ=self.extra_environ_admin, status=404)
        assert json.loads(response.body)['error'] == \
            u'There is no application settings with id %s' % id
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('applicationsetting', id=''), status=404,
                                   extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Unauthorized delete attempt as contributor
        response = self.app.post(url('applicationsettings'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        application_settings_count = new_application_settings_count
        new_application_settings_count = Session.query(ApplicationSettings).count()
        assert resp['object_language_name'] == u'test_delete object language name'
        assert new_application_settings_count == application_settings_count + 1
        response = self.app.delete(url('applicationsetting', id=resp['id']),
            headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

    @nottest
    def test_show(self):
        """Tests that GET /applicationsettings/id returns the JSON application settings object with id=id
        or a 404 status code depending on whether the id is valid or
        invalid/unspecified, respectively.
        """

        # Invalid id
        id = 100000000000
        response = self.app.get(url('applicationsetting', id=id),
                            extra_environ=self.extra_environ_admin, status=404)
        assert json.loads(response.body)['error'] == u'There is no application settings with id %s' % id
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('applicationsetting', id=''), status=404,
                                extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Add the default application settings.
        application_settings = add_default_application_settings()
        application_settings = h.get_application_settings()
        application_settings_id = application_settings.id

        # Valid id
        response = self.app.get(url('applicationsetting', id=application_settings_id),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert type(resp) == type({})
        assert resp['object_language_name'] == \
            application_settings.object_language_name
        assert resp['storage_orthography']['name'] == \
            application_settings.storage_orthography.name

    @nottest
    def test_edit(self):
        """Tests that GET /applicationsettings/id/edit returns a JSON object for editing an existing application settings.

        The JSON object is of the form {application_settings: {...}, data: {...}}
        or {'error': '...'} (and a 404 status code) depending on whether the id
        is valid or invalid/unspecified, respectively.
        """

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(
            url('edit_applicationsetting', id=100000000000), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id: expect 404 Not Found
        id = 100000000000
        response = self.app.get(url('edit_applicationsetting', id=id),
                            extra_environ=self.extra_environ_admin, status=404)
        assert json.loads(response.body)['error'] == \
            u'There is no application settings with id %s' % id
        assert response.content_type == 'application/json'

        # No id: expect 404 Not Found
        response = self.app.get(url('edit_applicationsetting', id=''),
            status=404, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Add the default application settings.
        application_settings = add_default_application_settings()
        application_settings = h.get_application_settings()
        application_settings_id = application_settings.id

        # Valid id
        response = self.app.get(url('edit_applicationsetting', id=application_settings_id),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert type(resp) == type({})
        assert resp['application_settings']['object_language_name'] == \
            application_settings.object_language_name

        # Valid id with GET params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetime_modified value of the
        #    store in question.

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'languages': h.get_languages(),
            'users': h.get_mini_dicts_getter('User')(),
            'orthographies': h.get_mini_dicts_getter('Orthography')()
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        params = {
            # Value is a non-empty string: 'users' will be in response.
            'users': 'give me some users!',
            # Value is empty string: 'languages' will not be in response.
            'languages': '',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Orthography.datetime_modified value: 'orthographies' *will*
            # be in the response.
            'orthographies': datetime.datetime.utcnow().isoformat(),
        }
        response = self.app.get(url('edit_applicationsetting', id=application_settings_id), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['data']['users'] == data['users']
        assert resp['data']['languages'] == []
        assert resp['data']['orthographies'] == data['orthographies']

        # Invalid id with GET params.  It should still return a 404 Not Found.
        params = {
            # If id were valid, this would cause a users array to be returned also.
            'users': 'True',
        }
        response = self.app.get(
            url('edit_applicationsetting', id=id), params,
            extra_environ=self.extra_environ_admin, status=404)
        assert json.loads(response.body)['error'] == \
            u'There is no application settings with id %s' % id
