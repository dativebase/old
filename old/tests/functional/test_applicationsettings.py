import datetime
import logging
import simplejson as json
from nose.tools import nottest

from old.tests import *
from old.model import ApplicationSettings, User, Orthography
from old.model.meta import Session
import old.lib.helpers as h

log = logging.getLogger(__name__)


def addDefaultApplicationSettings():
    """Add the default application settings to the database."""
    orthography1 = h.generateDefaultOrthography1()
    orthography2 = h.generateDefaultOrthography2()
    contributor = Session.query(User).filter(User.role==u'contributor').first()
    applicationSettings = h.generateDefaultApplicationSettings([orthography1, orthography2], [contributor])
    Session.add(applicationSettings)
    Session.commit()
    return applicationSettings


class TestApplicationsettingsController(TestController):

    createParams = {
        'objectLanguageName': u'',
        'objectLanguageId': u'',
        'metalanguageName': u'',
        'metalanguageId': u'',
        'metalanguageInventory': u'',
        'orthographicValidation': u'None', # Value should be one of [u'None', u'Warning', u'Error']
        'narrowPhoneticInventory': u'',
        'narrowPhoneticValidation': u'None',
        'broadPhoneticInventory': u'',
        'broadPhoneticValidation': u'None',
        'morphemeBreakIsOrthographic': u'',
        'morphemeBreakValidation': u'None',
        'phonemicInventory': u'',
        'morphemeDelimiters': u'',
        'punctuation': u'',
        'grammaticalities': u'',
        'unrestrictedUsers': [],        # A list of user ids
        'storageOrthography': u'',        # An orthography id
        'inputOrthography': u'',          # An orthography id
        'outputOrthography': u'',         # An orthography id
    }

    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language and User
    def tearDown(self):
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that GET /applicationsettings returns a JSON array of application settings objects."""

        """
        # Add an empty application settings.
        applicationSettings = ApplicationSettings()
        Session.add(applicationSettings)
        Session.commit()

        response = self.app.get(url('applicationsettings'),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        log.debug(resp)
        assert type(resp) == type([])
        assert len(resp) == 1
        assert resp[0]['objectLanguageName'] == None
        assert resp[0]['storageOrthography'] == None
        assert resp[0]['unrestrictedUsers'] == []
        assert response.content_type == 'application/json'
        """

        # Add the default application settings.
        applicationSettings = addDefaultApplicationSettings()

        response = self.app.get(url('applicationsettings'),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['objectLanguageName'] == applicationSettings.objectLanguageName
        assert resp[0]['storageOrthography']['name'] == applicationSettings.storageOrthography.name
        assert resp[0]['unrestrictedUsers'][0]['role'] == applicationSettings.unrestrictedUsers[0].role

    #@nottest
    def test_create(self):
        """Tests that POST /applicationsettings correctly creates a new application settings."""

        # Add some orthographies.
        orthography1 = h.generateDefaultOrthography1()
        orthography2 = h.generateDefaultOrthography2()
        Session.add_all([orthography1, orthography2])
        Session.commit()
        orthographies = [orthography1.id, orthography2.id]
        orthography1Id = orthography1.id
        orthography2Id = orthography2.id
        orthography2Orthography = orthography2.orthography

        params = self.createParams.copy()
        params.update({
            'objectLanguageName': u'test_create object language name',
            'objectLanguageId': u'tco',
            'metalanguageName': u'test_create metalanguage name',
            'metalanguageId': u'tcm',
            'orthographicValidation': u'Warning',
            'narrowPhoneticValidation': u'Error',
            'morphemeBreakIsOrthographic': False,
            'morphemeDelimiters': u'-,+',
            'punctuation': u'!?.,;:-_',
            'grammaticalities': u'*,**,***,?,??,???,#,##,###',
            'unrestrictedUsers': [Session.query(User).filter(
                User.role==u'viewer').first().id],
            'storageOrthography': orthography2Id,
            'inputOrthography': orthography2Id,
            'outputOrthography': orthography2Id
        })
        params = json.dumps(params)

        response = self.app.post(url('applicationsettings'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['objectLanguageName'] == u'test_create object language name'
        assert resp['morphemeBreakIsOrthographic'] is False
        assert resp['storageOrthography']['orthography'] == orthography2Orthography
        assert resp['unrestrictedUsers'][0]['firstName'] == u'Viewer'
        assert 'password' not in resp['unrestrictedUsers'][0]
        assert response.content_type == 'application/json'

        # Attempt the same above creation as a contributor and expect to fail.
        response = self.app.post(url('applicationsettings'), params,
            self.json_headers, self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

    #@nottest
    def test_create_invalid(self):
        """Tests that POST /applicationsettings responds with an appropriate error when invalid params are submitted in the request."""

        params = self.createParams.copy()
        params.update({
            'objectLanguageName': u'!' * 256,   # too long
            'objectLanguageId': u'too long',    # too long also
            'orthographicValidation': u'No Way!', # not a valid value
            # formencode.validators.StringBoolean accepts 'true', 'false' (with
            # any character in uppercase) as well as any int or float.  'Truish'
            # is unacceptable.
            'morphemeBreakIsOrthographic': u'Truish',
            'storageOrthography': 'accept me!'  # integer (orth.id) required
        })
        params = json.dumps(params)
        response = self.app.post(url('applicationsettings'), params,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['errors']['objectLanguageId'] == \
            u'Enter a value not more than 3 characters long'
        assert resp['errors']['objectLanguageName'] == \
            u'Enter a value not more than 255 characters long'
        assert u'Value must be one of: None; Warning; Error' in \
            resp['errors']['orthographicValidation']
        assert u"Value should be 'true' or 'false'" in \
            resp['errors']['morphemeBreakIsOrthographic']
        assert resp['errors']['storageOrthography'] == \
            u'Please enter an integer value'

    #@nottest
    def test_new(self):
        """Tests that GET /applicationsettings/new returns an appropriate JSON object for creating a new application settings object.

        The properties of the JSON object are 'languages', 'users' and
        'orthographies' and their values are arrays/lists.
        """

        # Add some orthographies.
        orthography1 = h.generateDefaultOrthography1()
        orthography2 = h.generateDefaultOrthography2()
        Session.add_all([orthography1, orthography2])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'languages': h.getLanguages(),
            'users': h.getMiniDictsGetter('User')(),
            'orthographies': h.getMiniDictsGetter('Orthography')()
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
        #    string that matches the most recent datetimeModified value of the
        #    store in question.
        params = {
            # Value is empty string: 'languages' will not be in response.
            'languages': '',
            # Value is any string: 'users' will be in response.
            'users': 'anything can go here!',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Orthography.datetimeModified value: 'orthographies' *will*
            # be in the response.
            'orthographies': datetime.datetime.utcnow().isoformat(),
        }
        response = self.app.get(url('new_applicationsetting'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['languages'] == []
        assert resp['users'] == data['users']
        assert resp['orthographies'] == data['orthographies']

    #@nottest
    def test_update(self):
        """Tests that PUT /applicationsettings/id correctly updates an existing application settings."""

        applicationSettingsCount = Session.query(
            ApplicationSettings).count()
        contributorId = Session.query(User).filter(User.role==u'contributor').first().id

        # Create an application settings to update.
        params = self.createParams.copy()
        params.update({
            'objectLanguageName': u'test_update object language name',
            'objectLanguageId': u'tuo',
            'metalanguageName': u'test_update metalanguage name',
            'metalanguageId': u'tum',
            'orthographicValidation': u'None',
            'narrowPhoneticValidation': u'Warning',
            'morphemeBreakIsOrthographic': True,
            'morphemeDelimiters': u'+',
            'punctuation': u'!.;:',
            'grammaticalities': u'*,**,?,??,#,##',
            'unrestrictedUsers': [contributorId]
        })
        params = json.dumps(params)
        response = self.app.post(url('applicationsettings'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        id = int(resp['id'])
        newApplicationSettingsCount = Session.query(ApplicationSettings).count()
        assert resp['objectLanguageName'] == u'test_update object language name'
        assert resp['unrestrictedUsers'][0]['role'] == u'contributor'
        assert newApplicationSettingsCount == applicationSettingsCount + 1

        # Update the application settings we just created but expect to fail
        # because the unrestricted users ids are invalid.
        params = self.createParams.copy()
        params.update({
            'objectLanguageName': u'Updated!',
            'unrestrictedUsers': [2000, 5000],
            'morphemeDelimiters': u'-,='
        })
        params = json.dumps(params)
        response = self.app.put(url('applicationsetting', id=id), params,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        applicationSettingsCount = newApplicationSettingsCount
        newApplicationSettingsCount = Session.query(ApplicationSettings).count()
        assert resp['errors']['unrestrictedUsers'] == [u"There is no user with id 2000.", u"There is no user with id 5000."]
        assert newApplicationSettingsCount == applicationSettingsCount
        assert response.content_type == 'application/json'

        # Update the application settings.
        params = self.createParams.copy()
        params.update({
            'objectLanguageName': u'Updated!',
            'unrestrictedUsers': [contributorId],
            'morphemeDelimiters': u'-,='
        })
        params = json.dumps(params)
        response = self.app.put(url('applicationsetting', id=id), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        applicationSettingsCount = newApplicationSettingsCount
        newApplicationSettingsCount = Session.query(ApplicationSettings).count()
        assert resp['objectLanguageName'] == u'Updated!'
        assert newApplicationSettingsCount == applicationSettingsCount
        assert response.content_type == 'application/json'

        # Attempt an update with no new data -- expect a 400 status code where
        # the response body is a JSON object with an appropriate 'error'
        # attribute.
        response = self.app.put(url('applicationsetting', id=id), params,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'the submitted data were not new' in resp['error']

        # Unauthorized update attempt as contributor
        params = self.createParams.copy()
        params.update({
            'objectLanguageName': u'Updated by a contrib!',
            'unrestrictedUsers': [contributorId],
            'morphemeDelimiters': u'-,='
        })
        params = json.dumps(params)
        response = self.app.put(url('applicationsetting', id=id), params,
                        self.json_headers, self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /applicationsettings/id deletes the application settings with id=id and returns a JSON representation.

        If the id is invalid or unspecified, then JSON null or a 404 status code
        are returned, respectively.
        """

        # Count the original number of application settings.
        applicationSettingsCount = Session.query(
            ApplicationSettings).count()

        # Add an orthography.
        orthography1 = h.generateDefaultOrthography1()
        Session.add(orthography1)
        Session.commit()
        orthography1 = h.getOrthographies()[0]
        orthography1Id = orthography1.id
        orthography1 = Session.query(Orthography).get(orthography1Id)
        orthography1Orthography = orthography1.orthography

        # First create an application settings to delete.
        params = self.createParams.copy()
        params.update({
            'objectLanguageName': u'test_delete object language name',
            'objectLanguageId': u'tdo',
            'metalanguageName': u'test_delete metalanguage name',
            'metalanguageId': u'tdm',
            'storageOrthography': orthography1Id,
            'morphemeDelimiters': u'-'
        })
        params = json.dumps(params)
        response = self.app.post(url('applicationsettings'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newApplicationSettingsCount = Session.query(
            ApplicationSettings).count()
        assert resp['objectLanguageName'] == u'test_delete object language name'
        assert newApplicationSettingsCount == applicationSettingsCount + 1

        # Delete the application settings we just created
        response = self.app.delete(
            url('applicationsetting', id=resp['id']),
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newApplicationSettingsCount = Session.query(ApplicationSettings).count()
        assert newApplicationSettingsCount == applicationSettingsCount
        assert response.content_type == 'application/json'
        # The deleted application settings will be returned to us, so the
        # assertions from above should still hold true.
        assert resp['objectLanguageName'] == u'test_delete object language name'

        # Trying to get the deleted form from the db should return None.
        deletedApplicationSettings = Session.query(
            ApplicationSettings).get(resp['id'])
        assert deletedApplicationSettings == None

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
        applicationSettingsCount = newApplicationSettingsCount
        newApplicationSettingsCount = Session.query(ApplicationSettings).count()
        assert resp['objectLanguageName'] == u'test_delete object language name'
        assert newApplicationSettingsCount == applicationSettingsCount + 1
        response = self.app.delete(url('applicationsetting', id=resp['id']),
            headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

    #@nottest
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
        applicationSettings = addDefaultApplicationSettings()
        applicationSettings = h.getApplicationSettings()
        applicationSettingsId = applicationSettings.id

        # Valid id
        response = self.app.get(url('applicationsetting', id=applicationSettingsId),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert type(resp) == type({})
        assert resp['objectLanguageName'] == \
            applicationSettings.objectLanguageName
        assert resp['storageOrthography']['name'] == \
            applicationSettings.storageOrthography.name

    #@nottest
    def test_edit(self):
        """Tests that GET /applicationsettings/id/edit returns a JSON object for editing an existing application settings.

        The JSON object is of the form {applicationSettings: {...}, data: {...}}
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
        applicationSettings = addDefaultApplicationSettings()
        applicationSettings = h.getApplicationSettings()
        applicationSettingsId = applicationSettings.id

        # Valid id
        response = self.app.get(url('edit_applicationsetting', id=applicationSettingsId),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert type(resp) == type({})
        assert resp['applicationSettings']['objectLanguageName'] == \
            applicationSettings.objectLanguageName

        # Valid id with GET params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetimeModified value of the
        #    store in question.

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'languages': h.getLanguages(),
            'users': h.getMiniDictsGetter('User')(),
            'orthographies': h.getMiniDictsGetter('Orthography')()
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
            # recent Orthography.datetimeModified value: 'orthographies' *will*
            # be in the response.
            'orthographies': datetime.datetime.utcnow().isoformat(),
        }
        response = self.app.get(url('edit_applicationsetting', id=applicationSettingsId), params,
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
