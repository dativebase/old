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
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import User
from onlinelinguisticdatabase.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


class TestUsersController(TestController):

    here = appconfig('config:test.ini', relative_to='.')['here']
    researchersPath = os.path.join(here, 'files', 'researchers')

    createParams = {
        'username': u'',
        'password': u'',
        'password_confirm': u'',
        'firstName': u'',
        'lastName': u'',
        'email': u'',
        'affiliation': u'',
        'role': u'',
        'markupLanguage': u'',
        'pageContent': u'',
        'inputOrthography': None,
        'outputOrthography': None
    }

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language; recreate the users.
    def tearDown(self):
        h.clearAllModels()
        h.destroyAllResearcherDirectories()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    @nottest
    def test_index(self):
        """Tests that GET /users returns an array of all users and that orderBy and pagination parameters work correctly."""

        # Add 100 users.
        def createUserFromIndex(index):
            user = model.User()
            user.username = u'user_%d' % index
            user.password = u'Aaaaaa_%d' % index
            user.firstName = u'John%d' % index
            user.lastName = u'Doe'
            user.email = u'john.doe@gmail.com'
            user.role = u'viewer'
            return user
        users = [createUserFromIndex(i) for i in range(1, 101)]
        Session.add_all(users)
        Session.commit()
        users = h.getUsers(True)
        usersCount = len(users)

        # Test that GET /users gives us all of the users.
        response = self.app.get(url('users'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == usersCount
        assert resp[3]['firstName'] == u'John1'
        assert resp[0]['id'] == users[0].id
        assert 'password' not in resp[3]
        assert 'username' not in resp[3]
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('users'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['firstName'] == users[46].firstName
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'User', 'orderByAttribute': 'username',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('users'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted(users, key=lambda u: u.username, reverse=True)
        assert [u.id for u in resultSet] == [u['id'] for u in resp]
        assert response.content_type == 'application/json'

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'User', 'orderByAttribute': 'username',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('users'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46].firstName == resp['items'][0]['firstName']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'User', 'orderByAttribute': 'username',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('users'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Userist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('users'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == users[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('users'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('users'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /users creates a new user
        or returns an appropriate error if the input is invalid.
        """

        # Attempt to create a user as a contributor and expect to fail
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Create a valid one
        originalResearchersDirectory = os.listdir(self.researchersPath)
        originalUserCount = Session.query(User).count()
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newUserCount = Session.query(User).count()
        newResearchersDirectory = os.listdir(self.researchersPath)
        researchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert newUserCount == originalUserCount + 1
        assert resp['username'] == u'johndoe'
        assert resp['email'] == u'john.doe@gmail.com'
        assert 'password' not in resp
        assert newResearchersDirectory != originalResearchersDirectory
        assert u'johndoe' in newResearchersDirectory
        assert response.content_type == 'application/json'

        # Invalid because username is not unique
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Zzzzzz_1',
            'password_confirm': u'Zzzzzz_1',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        researchersDirectory = newResearchersDirectory
        newResearchersDirectory = os.listdir(self.researchersPath)
        newResearchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert researchersDirectory == newResearchersDirectory
        assert researchersDirectoryMTime == newResearchersDirectoryMTime
        assert newUserCount == userCount
        assert resp['errors'] == u'The username johndoe is already taken.'
        assert response.content_type == 'application/json'

        # Invalid because username contains illicit characters
        params = self.createParams.copy()
        params.update({
            'username': u'johannes dough',
            'password': u'Zzzzzz_1',
            'password_confirm': u'Zzzzzz_1',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u'The username johannes dough is invalid; only letters of the English alphabet, numbers and the underscore are permitted.'
        assert response.content_type == 'application/json'

        # Invalid because username must be a non-empty string
        params = self.createParams.copy()
        params.update({
            'username': u'',
            'password': u'Zzzzzz_1',
            'password_confirm': u'Zzzzzz_1',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u'A username is required when creating a new user.'
        assert response.content_type == 'application/json'

        params = self.createParams.copy()
        params.update({
            'username': None,
            'password': u'Zzzzzz_1',
            'password_confirm': u'Zzzzzz_1',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u'A username is required when creating a new user.'
        assert response.content_type == 'application/json'

        # Invalid because username and password are both too long.  Notice how the space in the
        # username does not raise an error because the chained validators are not
        # called
        params = self.createParams.copy()
        params.update({
            'username': u'johannes dough' * 200,
            'password': u'Zzzzzz_1' * 200,
            'password_confirm': u'Zzzzzz_1' * 200,
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors']['username'] == u'Enter a value not more than 255 characters long'
        assert resp['errors']['password'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

        # Invalid because password and password_confirm do not match.
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Zzzzzz_1',
            'password_confirm': u'Zzzzzzx_1',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u'The password and password_confirm values do not match.'
        assert response.content_type == 'application/json'

        # Invalid because no password was provided.
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'',
            'password_confirm': u'',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u'A password is required when creating a new user.'
        assert response.content_type == 'application/json'

        # Invalid because no password was provided.
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': [],
            'password_confirm': [],
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u'A password is required when creating a new user.'
        assert response.content_type == 'application/json'

        # Invalid because the password is too short
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'aA_9',
            'password_confirm': u'aA_9',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u' '.join([
            u'The submitted password is invalid; valid passwords contain at least 8 characters',
            u'and either contain at least one character that is not in the printable ASCII range',
            u'or else contain at least one symbol, one digit, one uppercass letter and one lowercase letter.'])
        assert response.content_type == 'application/json'

        # Invalid because the password does not contain an uppercase printable ASCII character
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'abcdefg_9',
            'password_confirm': u'abcdefg_9',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u' '.join([
            u'The submitted password is invalid; valid passwords contain at least 8 characters',
            u'and either contain at least one character that is not in the printable ASCII range',
            u'or else contain at least one symbol, one digit, one uppercass letter and one lowercase letter.'])

        # Invalid because the password does not contain a lowercase printable ASCII character
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'ABCDEFG_9',
            'password_confirm': u'ABCDEFG_9',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u' '.join([
            u'The submitted password is invalid; valid passwords contain at least 8 characters',
            u'and either contain at least one character that is not in the printable ASCII range',
            u'or else contain at least one symbol, one digit, one uppercass letter and one lowercase letter.'])

        # Invalid because the password does not contain a symbol from the printable ASCII character range
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'abcdefgH9',
            'password_confirm': u'abcdefgH9',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u' '.join([
            u'The submitted password is invalid; valid passwords contain at least 8 characters',
            u'and either contain at least one character that is not in the printable ASCII range',
            u'or else contain at least one symbol, one digit, one uppercass letter and one lowercase letter.'])
        assert response.content_type == 'application/json'

        # Invalid because the password does not contain a digit
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'abcdefgH.',
            'password_confirm': u'abcdefgH.',
            'firstName': u'Johannes',
            'lastName': u'Dough',
            'email': u'johannes.dough@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors'] == u' '.join([
            u'The submitted password is invalid; valid passwords contain at least 8 characters',
            u'and either contain at least one character that is not in the printable ASCII range',
            u'or else contain at least one symbol, one digit, one uppercass letter and one lowercase letter.'])
        assert response.content_type == 'application/json'

        # Valid user: the password contains a unicode character
        researchersDirectory = os.listdir(self.researchersPath)
        researchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        sleep(1)
        params = self.createParams.copy()
        params.update({
            'username': u'aadams',
            'password': u'abcde\u0301fgh',
            'password_confirm': u'abcde\u0301fgh',
            'firstName': u'Alexander',
            'lastName': u'Adams',
            'email': u'aadams@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        newResearchersDirectory = os.listdir(self.researchersPath)
        newResearchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert u'aadams' not in researchersDirectory
        assert u'aadams' in newResearchersDirectory
        assert researchersDirectoryMTime != newResearchersDirectoryMTime
        assert newUserCount == userCount + 1
        assert resp['firstName'] == u'Alexander'
        assert u'password' not in resp
        assert response.content_type == 'application/json'

        # Invalid user: firstName is empty, email is invalid, affilication is too
        # long, role is unrecognized, inputOrthography is nonexistent, markupLanguage is unrecognized.
        params = self.createParams.copy()
        params.update({
            'username': u'xyh',
            'password': u'abcde\u0301fgh',
            'password_confirm': u'abcde\u0301fgh',
            'firstName': u'',
            'lastName': u'Yetzer-Hara',
            'affiliation': u'here, there, everywhere, ' * 200,
            'email': u'paradoxofevil@gmail',
            'role': u'master',
            'markupLanguage': u'markdownandupanddown',
            'pageContent': u'My OLD Page\n===============\n\nWhat a great linguistic fieldwork application!\n\n',
            'inputOrthography': 1234
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount
        assert resp['errors']['firstName'] == u'Please enter a value'
        assert resp['errors']['email'] == u'The domain portion of the email address is invalid (the portion after the @: gmail)'
        assert resp['errors']['affiliation'] == u'Enter a value not more than 255 characters long'
        assert resp['errors']['role'] == u"Value must be one of: viewer; contributor; administrator (not u'master')"
        assert resp['errors']['inputOrthography'] == u'There is no orthography with id 1234.'
        assert resp['errors']['markupLanguage'] == u"Value must be one of: markdown; reStructuredText (not u'markdownandupanddown')"
        assert response.content_type == 'application/json'

        # Valid user: all fields have valid values
        orthography1 = h.generateDefaultOrthography1()
        orthography2 = h.generateDefaultOrthography2()
        Session.add_all([orthography1, orthography2])
        Session.commit()
        orthography1Id = orthography1.id
        orthography2Id = orthography2.id
        params = self.createParams.copy()
        params.update({
            'username': u'alyoshas',
            'password': u'xY9.Bfx_J Jre\u0301',
            'password_confirm': u'xY9.Bfx_J Jre\u0301',
            'firstName': u'Alexander',
            'lastName': u'Solzhenitsyn',
            'email': u'amanaplanacanalpanama@gmail.com',
            'affiliation': u'Moscow State University',
            'role': u'contributor',
            'markupLanguage': u'markdown',
            'pageContent': u'My OLD Page\n===============\n\nWhat a great linguistic fieldwork application!\n\n',
            'inputOrthography': orthography1Id,
            'outputOrthography': orthography2Id
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert newUserCount == userCount + 1
        assert resp['username'] == u'alyoshas'
        assert resp['firstName'] == u'Alexander'
        assert resp['lastName'] == u'Solzhenitsyn'
        assert resp['email'] == u'amanaplanacanalpanama@gmail.com'
        assert resp['affiliation'] == u'Moscow State University'
        assert resp['role'] == u'contributor'
        assert resp['markupLanguage'] == u'markdown'
        assert resp['pageContent'] == u'My OLD Page\n===============\n\nWhat a great linguistic fieldwork application!\n\n'
        assert resp['html'] == h.getHTMLFromContents(resp['pageContent'], 'markdown')
        assert resp['inputOrthography']['id'] == orthography1Id
        assert resp['outputOrthography']['id'] == orthography2Id
        assert response.content_type == 'application/json'

    @nottest
    def test_new(self):
        """Tests that GET /users/new returns the data necessary to create a new user.

        The properties of the JSON object are 'roles', 'orthographies' and
        'markupLanguages' and their values are arrays/lists.
        """

        # A contributor (or a viewer) should return a 403 status code on the
        # new action, which requires an administrator.
        response = self.app.get(url('new_user'), extra_environ=self.extra_environ_contrib,
                                status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        orthography1 = h.generateDefaultOrthography1()
        orthography2 = h.generateDefaultOrthography2()
        Session.add_all([applicationSettings, orthography1, orthography2])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'orthographies': h.getMiniDictsGetter('Orthography')(),
            'roles': h.userRoles,
            'markupLanguages': h.markupLanguages
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # GET /users/new without params.  Without any GET params, /files/new
        # should return a JSON array for every store.
        response = self.app.get(url('new_user'),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['orthographies'] == data['orthographies']
        assert resp['roles'] == data['roles']
        assert resp['markupLanguages'] == data['markupLanguages']
        assert response.content_type == 'application/json'

        # GET /new_file with params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetimeModified value of the
        #    store in question.
        params = {
            # Value is any string: 'orthographies' will be in response.
            'orthographies': 'anything can go here!'
        }
        response = self.app.get(url('new_user'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['orthographies'] == data['orthographies']
        assert resp['roles'] == data['roles']
        assert resp['markupLanguages'] == data['markupLanguages']
        assert response.content_type == 'application/json'

        params = {
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Orthography.datetimeModified value: 'orthographies' *will* be in
            # response.
            'orthographies': datetime.datetime.utcnow().isoformat()
        }
        response = self.app.get(url('new_user'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['orthographies'] == data['orthographies']
        assert resp['roles'] == data['roles']
        assert resp['markupLanguages'] == data['markupLanguages']
        assert response.content_type == 'application/json'

        params = {
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent Orthography.datetimeModified value: 'orthographies' will *not* be in response.
            'orthographies': h.getMostRecentModificationDatetime('Orthography').isoformat()
        }
        response = self.app.get(url('new_user'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['orthographies'] == []
        assert resp['roles'] == data['roles']
        assert resp['markupLanguages'] == data['markupLanguages']
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /users/id updates the user with id=id."""

        defaultContributorId = Session.query(User).filter(User.role==u'contributor').first().id
        def_contrib_environ = {'test.authentication.id': defaultContributorId}

        # Create a user to update.
        originalResearchersDirectory = os.listdir(self.researchersPath)
        originalUserCount = Session.query(User).count()
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        userId = resp['id']
        datetimeModified = resp['datetimeModified']
        newUserCount = Session.query(User).count()
        newResearchersDirectory = os.listdir(self.researchersPath)
        researchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert newUserCount == originalUserCount + 1
        assert resp['username'] == u'johndoe'
        assert resp['email'] == u'john.doe@gmail.com'
        assert 'password' not in resp
        assert newResearchersDirectory != originalResearchersDirectory
        assert u'johndoe' in newResearchersDirectory
        assert response.content_type == 'application/json'

        # Update the user
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'username': u'johnbuck',    # Admins CAN change usernames
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'contributor'  # Admins CAN change roles
        })
        params = json.dumps(params)
        response = self.app.put(url('user', id=userId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        newDatetimeModified = resp['datetimeModified']
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        researchersDirectory = newResearchersDirectory
        newResearchersDirectory = os.listdir(self.researchersPath)
        assert userCount == newUserCount
        assert newDatetimeModified != datetimeModified
        assert resp['username'] == u'johnbuck'
        assert resp['role'] == u'contributor'
        assert resp['lastName'] == u'Doe'
        assert researchersDirectory != newResearchersDirectory
        assert u'johndoe' in researchersDirectory and u'johndoe' not in newResearchersDirectory
        assert u'johnbuck' in newResearchersDirectory and u'johnbuck' not in researchersDirectory
        assert response.content_type == 'application/json'

        # Attempt to update the user as a contributor and expect to fail
        params = self.createParams.copy()
        params.update({
            'username': u'johnbuck',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Buck',        # here is the attempted change
            'email': u'john.doe@gmail.com',
            'role': u'contributor'
        })
        params = json.dumps(params)
        response = self.app.put(url('user', id=userId), params, self.json_headers,
                                 def_contrib_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Attempt to update the user as the user and expect to succeed
        user_environ = {'test.authentication.id': userId}
        params = self.createParams.copy()
        params.update({
            'username': u'johnbuck',
            'password': u'Zzzzzz.9',    # Change the password too
            'password_confirm': u'Zzzzzz.9',
            'firstName': u'John',
            'lastName': u'Buck',        # Now this change will succeed
            'email': u'john.doe@gmail.com',
            'role': u'contributor'
        })
        params = json.dumps(params)
        response = self.app.put(url('user', id=userId), params, self.json_headers,
                                 user_environ)
        resp = json.loads(response.body)
        userJustUpdated = Session.query(User).get(userId)
        assert resp['username'] == u'johnbuck'
        assert resp['lastName'] == u'Buck'
        assert h.encryptPassword(u'Zzzzzz.9', str(userJustUpdated.salt)) == userJustUpdated.password
        assert response.content_type == 'application/json'

        # Simulate a user attempting to update his username.  Expect to fail.
        params = self.createParams.copy()
        params.update({
            'username': u'iroc_z',  # Not permitted
            'password': u'Zzzzzz.9',
            'password_confirm': u'Zzzzzz.9',
            'firstName': u'John',
            'lastName': u'Buck',
            'email': u'john.doe@gmail.com',
            'role': u'contributor'
        })
        params = json.dumps(params)
        response = self.app.put(url('user', id=userId), params, self.json_headers,
                                 user_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors'] == u'Only administrators can update usernames.'
        assert response.content_type == 'application/json'

        # Simulate a user attempting to update his role.  Expect to fail.
        params = self.createParams.copy()
        params.update({
            'username': u'johnbuck',
            'password': u'Zzzzzz.9',
            'password_confirm': u'Zzzzzz.9',
            'firstName': u'John',
            'lastName': u'Buck',
            'email': u'john.doe@gmail.com',
            'role': u'administrator'    # Not permitted
        })
        params = json.dumps(params)
        response = self.app.put(url('user', id=userId), params, self.json_headers,
                                 user_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors'] == u'Only administrators can update roles.'
        assert response.content_type == 'application/json'

        # Update the user with empty values for username and password and expect
        # these fields to retain their original values.
        mdContents = u'\n'.join([
            'My Page',
            '=======',
            '',
            'Research Interests',
            '---------------------',
            '',
            '* Item 1',
            '* Item 2',
            ''
        ])
        params = self.createParams.copy()
        params.update({
            'firstName': u'John',
            'lastName': u'Buckley',         # Here is a change
            'email': u'john.doe@gmail.com',
            'role': u'contributor',
            'markupLanguage': u'markdown',  # Another change
            'pageContent': mdContents       # And another
        })
        params = json.dumps(params)
        response = self.app.put(url('user', id=userId), params, self.json_headers, user_environ)
        resp = json.loads(response.body)
        userJustUpdated = Session.query(User).get(userId)
        assert resp['username'] == u'johnbuck'
        assert resp['lastName'] == u'Buckley'
        assert h.encryptPassword(u'Zzzzzz.9', str(userJustUpdated.salt)) == userJustUpdated.password
        assert resp['html'] == h.getHTMLFromContents(mdContents, u'markdown')
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        params = self.createParams.copy()
        params.update({
            'firstName': u'John',
            'lastName': u'Buckley',
            'email': u'john.doe@gmail.com',
            'role': u'contributor',
            'markupLanguage': u'markdown',
            'pageContent': mdContents
        })
        params = json.dumps(params)
        response = self.app.put(url('user', id=userId), params, self.json_headers, user_environ, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /users/id deletes the user with id=id."""

        # Create a user to delete.
        originalResearchersDirectory = os.listdir(self.researchersPath)
        originalUserCount = Session.query(User).count()
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        userId = resp['id']
        datetimeModified = resp['datetimeModified']
        newUserCount = Session.query(User).count()
        newResearchersDirectory = os.listdir(self.researchersPath)
        researchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert newUserCount == originalUserCount + 1
        assert resp['username'] == u'johndoe'
        assert resp['email'] == u'john.doe@gmail.com'
        assert 'password' not in resp
        assert newResearchersDirectory != originalResearchersDirectory
        assert u'johndoe' in newResearchersDirectory

        # Write a file to the user's directory just to make sure that the deletion
        # works on a non-empty directory
        f = open(os.path.join(self.researchersPath, 'johndoe', 'test_file.txt'), 'w')
        f.write('Some content here.')
        f.close()
        assert u'test_file.txt' in os.listdir(os.path.join(self.researchersPath, 'johndoe'))

        # Now delete the user
        response = self.app.delete(url('user', id=userId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        researchersDirectory = newResearchersDirectory
        newResearchersDirectory = os.listdir(self.researchersPath)
        deletedUser = Session.query(User).get(userId)
        assert deletedUser is None
        assert newUserCount == userCount - 1
        assert resp['id'] == userId
        assert 'password' not in resp
        assert resp['username'] == u'johndoe'
        assert researchersDirectory != newResearchersDirectory
        assert u'johndoe' not in newResearchersDirectory and u'johndoe' in researchersDirectory
        assert response.content_type == 'application/json'

        # Again create a user to (attempt to) delete.
        originalResearchersDirectory = os.listdir(self.researchersPath)
        originalUserCount = Session.query(User).count()
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        userId = resp['id']
        datetimeModified = resp['datetimeModified']
        newUserCount = Session.query(User).count()
        newResearchersDirectory = os.listdir(self.researchersPath)
        researchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert newUserCount == originalUserCount + 1
        assert resp['username'] == u'johndoe'
        assert resp['email'] == u'john.doe@gmail.com'
        assert 'password' not in resp
        assert newResearchersDirectory != originalResearchersDirectory
        assert u'johndoe' in newResearchersDirectory
        assert response.content_type == 'application/json'

        # Show that a user cannot delete his own user object
        user_environ = {'test.authentication.id': userId}
        response = self.app.delete(url('user', id=userId), headers=self.json_headers,
            extra_environ=user_environ, status=403)
        resp = json.loads(response.body)
        userCount = newUserCount
        newUserCount = Session.query(User).count()
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('user', id=id), headers=self.json_headers,
            extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no user with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('user', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    @nottest
    def test_show(self):
        """Tests that GET /users/id returns the user with id=id or an appropriate error."""

        # Create a user to show.
        originalResearchersDirectory = os.listdir(self.researchersPath)
        originalUserCount = Session.query(User).count()
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        userId = resp['id']
        datetimeModified = resp['datetimeModified']
        newUserCount = Session.query(User).count()
        newResearchersDirectory = os.listdir(self.researchersPath)
        researchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert newUserCount == originalUserCount + 1
        assert resp['username'] == u'johndoe'
        assert resp['email'] == u'john.doe@gmail.com'
        assert 'password' not in resp
        assert newResearchersDirectory != originalResearchersDirectory
        assert u'johndoe' in newResearchersDirectory

        # Try to get a user using an invalid id
        id = 100000000000
        response = self.app.get(url('user', id=id), headers=self.json_headers,
                            extra_environ=self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert u'There is no user with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('user', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id (show that a viewer can GET a user too)
        response = self.app.get(url('user', id=userId), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert 'username' not in resp
        assert 'password' not in resp
        assert resp['email'] == u'john.doe@gmail.com'
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /users/id/edit returns a JSON object of data necessary to edit the user with id=id.

        The JSON object is of the form {'user': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Add some test data to the database.
        orthography1 = h.generateDefaultOrthography1()
        orthography2 = h.generateDefaultOrthography2()
        Session.add_all([orthography1, orthography2])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'orthographies': h.getMiniDictsGetter('Orthography')(),
            'roles': h.userRoles,
            'markupLanguages': h.markupLanguages
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # Create a user to edit.
        originalResearchersDirectory = os.listdir(self.researchersPath)
        originalUserCount = Session.query(User).count()
        params = self.createParams.copy()
        params.update({
            'username': u'johndoe',
            'password': u'Aaaaaa_1',
            'password_confirm': u'Aaaaaa_1',
            'firstName': u'John',
            'lastName': u'Doe',
            'email': u'john.doe@gmail.com',
            'role': u'viewer'
        })
        params = json.dumps(params)
        response = self.app.post(url('users'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        userId = resp['id']
        datetimeModified = resp['datetimeModified']
        newUserCount = Session.query(User).count()
        newResearchersDirectory = os.listdir(self.researchersPath)
        researchersDirectoryMTime = os.stat(self.researchersPath).st_mtime
        assert newUserCount == originalUserCount + 1
        assert resp['username'] == u'johndoe'
        assert resp['email'] == u'john.doe@gmail.com'
        assert 'password' not in resp
        assert newResearchersDirectory != originalResearchersDirectory
        assert u'johndoe' in newResearchersDirectory
        assert response.content_type == 'application/json'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_user', id=userId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_user', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no user with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_user', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == u'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id, admin
        response = self.app.get(url('edit_user', id=userId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['user']['username'] == u'johndoe'
        assert resp['data']['orthographies'] == data['orthographies']
        assert resp['data']['roles'] == data['roles']
        assert resp['data']['markupLanguages'] == data['markupLanguages']
        assert response.content_type == 'application/json'

        # Valid id, user self-editing, GET params
        user_environ = {'test.authentication.id': userId}
        params = {
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent Orthography.datetimeModified value: 'orthographies' will *not* be in response.
            'orthographies': h.getMostRecentModificationDatetime('Orthography').isoformat()
        }
        response = self.app.get(url('edit_user', id=userId), params,
            headers=self.json_headers, extra_environ=user_environ)
        resp = json.loads(response.body)
        assert resp['user']['username'] == u'johndoe'
        assert resp['data']['orthographies'] == []
        assert resp['data']['roles'] == data['roles']
        assert resp['data']['markupLanguages'] == data['markupLanguages']
        assert response.content_type == 'application/json'

        # Valid id but contributor -- expect to fail
        response = self.app.get(url('edit_user', id=userId),
            headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'
