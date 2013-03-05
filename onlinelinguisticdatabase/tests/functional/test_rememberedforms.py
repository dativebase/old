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
from time import sleep
from onlinelinguisticdatabase.tests import *
from nose.tools import nottest
import simplejson as json
import logging
from datetime import date, datetime, timedelta
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
import webtest

log = logging.getLogger(__name__)


# Global temporal objects -- useful for creating the data upon which to search
# and for formulating assertions about the results of those searches.
todayTimestamp = datetime.now()
dayDelta = timedelta(1)
yesterdayTimestamp = todayTimestamp - dayDelta
jan1 = date(2012, 01, 01)
jan2 = date(2012, 01, 02)
jan3 = date(2012, 01, 03)
jan4 = date(2012, 01, 04)

################################################################################
# Functions for creating & retrieving test data
################################################################################
def getUsers():
    users = h.getUsers()
    viewer = [u for u in users if u.role == u'viewer'][0]
    contributor = [u for u in users if u.role == u'contributor'][0]
    administrator = [u for u in users if u.role == u'administrator'][0]
    return viewer, contributor, administrator

def createTestModels(n=100):
    addTestModelsToSession('Tag', n, ['name'])
    addTestModelsToSession('Speaker', n, ['firstName', 'lastName', 'dialect'])
    addTestModelsToSession('Source', n, ['authorFirstName', 'authorLastName',
                                            'title'])
    addTestModelsToSession('ElicitationMethod', n, ['name'])
    addTestModelsToSession('SyntacticCategory', n, ['name'])
    addTestModelsToSession('File', n, ['name'])
    restrictedTag = h.generateRestrictedTag()
    Session.add(restrictedTag)
    Session.commit()

def addTestModelsToSession(modelName, n, attrs):
    for i in range(1, n + 1):
        m = getattr(model, modelName)()
        for attr in attrs:
            setattr(m, attr, u'%s %s' % (attr, i))
        Session.add(m)

def getTestModels():
    defaultModels = {
        'tags': h.getTags(),
        'speakers': h.getSpeakers(),
        'sources': h.getSources(),
        'elicitationMethods': h.getElicitationMethods(),
        'syntacticCategories': h.getSyntacticCategories(),
        'files': h.getFiles()
    }
    return defaultModels

def createTestForms(n=100):
    """Create n forms with various properties.  A testing ground for searches!
    """
    testModels = getTestModels()
    viewer, contributor, administrator = getUsers()
    restrictedTag = h.getRestrictedTag()
    for i in range(1, n + 1):
        f = model.Form()
        f.transcription = u'transcription %d' % i
        if i > 50:
            f.transcription = f.transcription.upper()
        f.morphemeBreak = u'morphemeBreak %d' % i
        f.morphemeGloss = u'morphemeGloss %d' % i
        f.comments = u'comments %d' % i
        f.speakerComments = u'speakerComments %d' % i
        f.morphemeBreakIDs = u'[[[]]]'
        f.morphemeGlossIDs = u'[[[]]]'
        tl = model.Translation()
        tl.transcription = u'translation %d' % i
        f.enterer = contributor
        f.syntacticCategory = testModels['syntacticCategories'][i - 1]
        if i > 75:
            f.phoneticTranscription = u'phoneticTranscription %d' % i
            f.narrowPhoneticTranscription = u'narrowPhoneticTranscription %d' % i
            t = testModels['tags'][i - 1]
            f.tags.append(t)
            tl.grammaticality = u'*'
        if i > 65 and i < 86:
            fi = testModels['files'][i - 1]
            f.files.append(fi)
        if i > 50:
            f.elicitor = contributor
            f.tags.append(restrictedTag)
            if i != 100:
                f.speaker = testModels['speakers'][0]
                f.datetimeModified = todayTimestamp
                f.datetimeEntered = todayTimestamp
        else:
            f.elicitor = administrator
            f.speaker = testModels['speakers'][-1]
            f.datetimeModified = yesterdayTimestamp
            f.datetimeEntered = yesterdayTimestamp
        if i < 26:
            f.elicitationMethod = testModels['elicitationMethods'][0]
            f.dateElicited = jan1
        elif i < 51:
            f.elicitationMethod = testModels['elicitationMethods'][24]
            f.dateElicited = jan2
        elif i < 76:
            f.elicitationMethod = testModels['elicitationMethods'][49]
            f.dateElicited = jan3
        else:
            f.elicitationMethod = testModels['elicitationMethods'][74]
            if i < 99:
                f.dateElicited = jan4
        if (i > 41 and i < 53) or i in [86, 92, 3]:
            f.source = testModels['sources'][i]
        if i != 87:
            f.translations.append(tl)
        if i == 79:
            tl = model.Translation()
            tl.transcription = u'translation %d the second' % i
            f.translations.append(tl)
            t = testModels['tags'][i - 2]
            f.tags.append(t)
        Session.add(f)
    Session.commit()

def createTestData(n=100):
    createTestModels(n)
    createTestForms(n)

def addSEARCHToWebTestValidMethods():
    new_valid_methods = list(webtest.lint.valid_methods)
    new_valid_methods.append('SEARCH')
    new_valid_methods = tuple(new_valid_methods)
    webtest.lint.valid_methods = new_valid_methods


class TestRememberedformsController(TestController):
    """This test suite is modelled on the test_forms_search and test_oldcollections_search
    pattern, i.e., an initialize "test" runs first and a clean up one runs at the
    end.  Also, the update test should run before the show and search tests because
    the former creates the remembered forms for the latter two to retrieve.
    """

    extra_environ_view = {'test.authentication.role': u'viewer',
                          'test.applicationSettings': True}
    extra_environ_contrib = {'test.authentication.role': u'contributor',
                             'test.applicationSettings': True}
    extra_environ_admin = {'test.authentication.role': u'administrator',
                           'test.applicationSettings': True}
    json_headers = {'Content-Type': 'application/json'}
    n = 100

    # The initialize "test" needs to run before all others
    #@nottest
    def test_a_initialize(self):
        """Initialize the database for /rememberedforms tests."""
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        createTestData(self.n)
        addSEARCHToWebTestValidMethods()

        # Create an application settings where the contributor is unrestricted
        viewer, contributor, administrator = getUsers()
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.unrestrictedUsers = [contributor]
        Session.add(applicationSettings)
        Session.commit()

    #@nottest
    # The update test needs to run before the show and search tests.
    def test_b_update(self):
        """Tests that PUT /rememberedforms/id correctly updates the set of forms remembered by the user with id=id."""
        forms = sorted(json.loads(json.dumps(h.getForms(), cls=h.JSONOLDEncoder)), key=lambda f: f['id'])
        viewer, contributor, administrator = getUsers()
        viewerId = viewer.id
        viewerDatetimeModified = viewer.datetimeModified
        contributorId = contributor.id
        administratorId = administrator.id

        ########################################################################
        # Viewer -- play with the viewer's remembered forms
        ########################################################################

        # Try to add every form in the database to the viewer's remembered forms.
        # Since the viewer is restricted (i.e., not unrestricted), only the
        # unrestricted forms will be added.
        sleep(1)
        params = json.dumps({'forms': [f['id'] for f in forms]})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                                params, self.json_headers, self.extra_environ_view)
        resp = json.loads(response.body)
        viewerRememberedForms = sorted(resp, key=lambda f: f['id'])
        resultSet = [f for f in forms if u'restricted' not in [t['name'] for t in f['tags']]]
        viewer, contributor, administrator = getUsers()
        newViewerDatetimeModified = viewer.datetimeModified
        assert newViewerDatetimeModified != viewerDatetimeModified
        assert set([f['id'] for f in resultSet]) == set([f['id'] for f in resp])
        assert response.content_type == 'application/json'


        # Try to clear the viewer's remembered forms as the contributor and
        # expect the request to be denied.
        params = json.dumps({'forms': []})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                params, self.json_headers, self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

        # Get the list of ids from the userforms relational table.  This is used
        # to show that resetting a user's rememberedForms attribute via SQLAlchemy
        # does not wastefully recreate all relations.  See below
        userForms = Session.query(model.UserForm).filter(model.UserForm.user_id==viewerId).all()
        originalUserFormIds = sorted([uf.id for uf in userForms])
        expectedNewUserFormIds = [uf.id for uf in userForms
                                  if uf.form_id != viewerRememberedForms[-1]['id']]

        # Remove the last of the viewer's remembered forms as the administrator.
        params = json.dumps({'forms': [f['id'] for f in viewerRememberedForms][:-1]})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                                params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = resultSet[:-1]
        assert set([f['id'] for f in resultSet]) == set([f['id'] for f in resp])
        assert response.content_type == 'application/json'

        # See what happens when a large list of remembered forms is altered like this;
        # are all the relations destroyed and recreated?
        # Get the list of ids from the userforms relational table
        userForms = Session.query(model.UserForm).filter(model.UserForm.user_id==viewerId).all()
        currentUserFormIds = sorted([uf.id for uf in userForms])
        assert set(expectedNewUserFormIds) == set(currentUserFormIds)

        # Attempted update fails: bad user id
        params = json.dumps({'forms': []})
        response = self.app.put(url(controller='rememberedforms', action='update', id=100896),
                params, self.json_headers, self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'There is no user with id 100896'

        # Attempted update fails: invalid array of form ids
        params = json.dumps({'forms': ['a', 1000000087654]})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['errors']['forms'] == [u'Please enter an integer value',
                                           u'There is no form with id 1000000087654.']

        # Attempted update fails: array of form ids is bad JSON
        params = json.dumps({'forms': []})[:-1]
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'JSON decode error: the parameters provided were not valid JSON.'

        # Clear the forms
        params = json.dumps({'forms': []})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        viewer = Session.query(model.User).filter(model.User.role==u'viewer').first()
        assert response.content_type == 'application/json'
        assert viewer.rememberedForms == []
        assert resp == []

        # Attempt to clear the forms again and fail because the submitted data are not new.
        params = json.dumps({'forms': []})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                params, self.json_headers, self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'The update request failed because the submitted data were not new.'

        # Attempt to add all unrestricted forms to the viewer's remembered forms.
        # Fail because unauthenticated.
        params = json.dumps({'forms': [f['id'] for f in forms]})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                                    params, self.json_headers, status=401)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'Authentication is required to access this resource.'

        # Finally for the viewer, re-add all unrestricted forms to the viewer's
        # remembered forms for subsequent searches and GETs.
        params = json.dumps({'forms': [f['id'] for f in forms]})
        response = self.app.put(url(controller='rememberedforms', action='update', id=viewerId),
                            params, self.json_headers, self.extra_environ_view)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        resultSet = [f for f in forms if u'restricted' not in [t['name'] for t in f['tags']]]
        assert set([f['id'] for f in resultSet]) == set([f['id'] for f in resp])

        ########################################################################
        # Contributor -- play with the contributor's remembered forms
        ########################################################################

        # The contributor is unrestricted.  Add all forms to this user's
        # remembered forms.
        params = json.dumps({'forms': [f['id'] for f in forms]})
        response = self.app.put(url(controller='rememberedforms', action='update', id=contributorId),
                            params, self.json_headers, self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert set([f['id'] for f in forms]) == set([f['id'] for f in resp])

        # Change the contributor's remembered forms to contain only the forms
        # with odd numbered ids.
        oddNumberedFormIds = [f['id'] for f in forms if f['id'] % 2 != 0]
        params = json.dumps({'forms': oddNumberedFormIds})
        response = self.app.put(url(controller='rememberedforms', action='update', id=contributorId),
                            params, self.json_headers, self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert set(oddNumberedFormIds) == set([f['id'] for f in resp])

        ########################################################################
        # Administrator -- play with the administrator's remembered forms
        ########################################################################

        # Make sure even an unrestricted contributor cannot update another user's
        # remembered forms.
        formIdsForAdmin = [f['id'] for f in forms if f['id'] % 2 != 0 and f['id'] > 25]
        params = json.dumps({'forms': formIdsForAdmin})
        response = self.app.put(url(controller='rememberedforms', action='update', id=administratorId),
                            params, self.json_headers, self.extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'You are not authorized to access this resource.'

        # The administrator's remembered forms are all the evenly id-ed ones with
        # ids greater than 25.
        formIdsForAdmin = [f['id'] for f in forms if f['id'] % 2 == 0 and f['id'] > 25]
        params = json.dumps({'forms': formIdsForAdmin})
        response = self.app.put(url(controller='rememberedforms', action='update', id=administratorId),
                            params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert set(formIdsForAdmin) == set([f['id'] for f in resp])

    #@nottest
    def test_c_show(self):
        """Tests that GET /rememberedforms/id returns an array of the forms remembered by the user with id=id."""
        forms = json.loads(json.dumps(h.getForms(), cls=h.JSONOLDEncoder))
        viewer, contributor, administrator = getUsers()
        viewerId = viewer.id
        contributorId = contributor.id
        administratorId = administrator.id

        ########################################################################
        # Viewer
        ########################################################################

        # Get the viewer's remembered forms (show that a contributor can do this)
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        resultSet = [f for f in forms if u'restricted' not in [t['name'] for t in f['tags']]]
        assert response.content_type == 'application/json'
        assert set([f['id'] for f in resultSet]) == set([f['id'] for f in resp])
        # Test the pagination and order by

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 7, 'page': 3}
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
                        paginator, headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert len(resp['items']) == 7
        assert resp['items'][0]['transcription'] == resultSet[14]['transcription']

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Form', 'orderByAttribute': 'transcription',
                     'orderByDirection': 'desc'}
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
                        orderByParams, headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        resultSetOrdered = sorted(resultSet, key=lambda f: f['transcription'], reverse=True)
        assert response.content_type == 'application/json'
        assert resultSetOrdered == resp

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Form', 'orderByAttribute': 'transcription',
                     'orderByDirection': 'desc', 'itemsPerPage': 7, 'page': 3}
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
                        params, headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert len(resp['items']) == 7
        assert resultSetOrdered[14]['transcription'] == resp['items'][0]['transcription']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Form', 'orderByAttribute': 'transcription',
                     'orderByDirection': 'descending'}
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
            orderByParams, headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=400)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Formosa', 'orderByAttribute': 'transcrumption',
                     'orderByDirection': 'desc'}
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
            orderByParams, headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp[0]['id'] == forms[0]['id']

        # Expect a 400 error when the paginator GET params are, empty, not
        # or integers that are less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
            paginator, headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url(controller='rememberedforms', action='show', id=viewerId),
            paginator, headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

        ########################################################################
        # Contributor
        ########################################################################

        # Get the contributor's remembered forms
        response = self.app.get(url(controller='rememberedforms', action='show', id=contributorId),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        resultSet = [f for f in forms if f['id'] % 2 != 0]
        assert response.content_type == 'application/json'
        assert set([f['id'] for f in resultSet]) == set([f['id'] for f in resp])

        # Invalid user id returns a 404 error
        response = self.app.get(url(controller='rememberedforms', action='show', id=200987654),
                headers=self.json_headers, extra_environ=self.extra_environ_contrib, status=404)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'There is no user with id 200987654'

        ########################################################################
        # Administrator
        ########################################################################

        # Get the administrator's remembered forms
        response = self.app.get(url(controller='rememberedforms', action='show', id=administratorId),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in forms if f['id'] % 2 == 0 and f['id'] > 25]
        assert response.content_type == 'application/json'
        assert set([f['id'] for f in resultSet]) == set([f['id'] for f in resp])

    #@nottest
    def test_d_search(self):
        """Tests that SEARCH /rememberedforms/id returns an array of the forms remembered by the user with id=id that match the search criteria.

        Here we show the somewhat complex interplay of the unrestricted users, the
        restricted tag and the rememberedForms relation between users and forms.
        """

        forms = json.loads(json.dumps(h.getForms(), cls=h.JSONOLDEncoder))
        viewer, contributor, administrator = getUsers()
        viewerId = viewer.id
        contributorId = contributor.id
        administratorId = administrator.id

        viewerRememberedForms = [f for f in forms
                                 if u'restricted' not in [t['name'] for t in f['tags']]]
        contributorRememberedForms = [f for f in forms if f['id'] % 2 != 0]
        administratorRememberedForms = [f for f in forms if f['id'] % 2 == 0 and f['id'] > 25]

        # The query we will use over and over again
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['Translation', 'transcription', 'like', '%1%'],
                ['not', ['Form', 'morphemeBreak', 'regex', '[18][5-7]']],
                ['or', [
                    ['Form', 'datetimeModified', '=', todayTimestamp.isoformat()],
                    ['Form', 'dateElicited', '=', jan1.isoformat()]]]]]}})
        # A slight variation on the above query so that searches on the admin's
        # remembered forms will return some values
        jsonQueryAdmin = json.dumps({'query': {'filter': [
            'and', [
                ['Translation', 'transcription', 'like', '%8%'],
                ['not', ['Form', 'morphemeBreak', 'regex', '[18][5-7]']],
                ['or', [
                    ['Form', 'datetimeModified', '=', todayTimestamp.isoformat()],
                    ['Form', 'dateElicited', '=', jan1.isoformat()]]]]]}})

        # The expected output of the above query on each of the user's remembered forms list
        resultSetViewer = [
            f for f in viewerRememberedForms if
            '1' in ' '.join([g['transcription'] for g in f['translations']]) and
            not re.search('[18][5-7]', f['morphemeBreak']) and
            (todayTimestamp.isoformat().split('.')[0] == f['datetimeModified'].split('.')[0] or
            (f['dateElicited'] and jan1.isoformat() == f['dateElicited']))]
        resultSetContributor = [
            f for f in contributorRememberedForms if
            '1' in ' '.join([g['transcription'] for g in f['translations']]) and
            not re.search('[18][5-7]', f['morphemeBreak']) and
            (todayTimestamp.isoformat().split('.')[0] == f['datetimeModified'].split('.')[0] or
            (f['dateElicited'] and jan1.isoformat() == f['dateElicited']))]
        resultSetAdministrator = [
            f for f in administratorRememberedForms if
            '8' in ' '.join([g['transcription'] for g in f['translations']]) and
            not re.search('[18][5-7]', f['morphemeBreak']) and
            (todayTimestamp.isoformat().split('.')[0] == f['datetimeModified'].split('.')[0] or
            (f['dateElicited'] and jan1.isoformat() == f['dateElicited']))]

        # Search the viewer's remembered forms as the viewer
        response = self.app.post(url('/rememberedforms/%d/search' % viewerId),
                        jsonQuery, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert [f['id'] for f in resultSetViewer] == [f['id'] for f in resp]
        assert response.content_type == 'application/json'
        assert resp

        # Perform the same search as above on the contributor's remembered forms,
        # as the contributor.
        response = self.app.request(url('/rememberedforms/%d' % contributorId),
                        method='SEARCH', body=jsonQuery, headers=self.json_headers,
                        environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert [f['id'] for f in resultSetContributor] == [f['id'] for f in resp]
        assert response.content_type == 'application/json'
        assert resp

        # Perform the same search as above on the contributor's remembered forms,
        # but search as the viewer and expect not to see the restricted forms,
        # i.e., those with ids > 50.
        response = self.app.post(url('/rememberedforms/%d/search' % contributorId),
                        jsonQuery, self.json_headers, self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = [f for f in resultSetContributor if
                     u'restricted' not in [t['name'] for t in f['tags']]]
        assert [f['id'] for f in resultSet] == [f['id'] for f in resp]
        assert response.content_type == 'application/json'
        assert resp

        # Perform the search on the administrator's remembered forms as the viewer.
        response = self.app.request(url('/rememberedforms/%d' % administratorId),
                        method='SEARCH', body=jsonQueryAdmin, headers=self.json_headers,
                        environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = [f for f in resultSetAdministrator if
                     u'restricted' not in [t['name'] for t in f['tags']]]
        assert [f['id'] for f in resultSet] == [f['id'] for f in resp]
        assert response.content_type == 'application/json'

        # Perform the search on the administrator's remembered forms as the contributor.
        response = self.app.post(url('/rememberedforms/%d/search' % administratorId),
                        jsonQueryAdmin, self.json_headers, self.extra_environ_contrib)
        resp = json.loads(response.body)
        resultSet = resultSetAdministrator
        assert [f['id'] for f in resultSet] == [f['id'] for f in resp]
        assert response.content_type == 'application/json'
        assert resp

        # Perform the search on the administrator's remembered forms as the administrator.
        response = self.app.request(url('/rememberedforms/%d' % administratorId),
                        method='SEARCH', body=jsonQueryAdmin, headers=self.json_headers,
                        environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = resultSetAdministrator
        assert [f['id'] for f in resultSet] == [f['id'] for f in resp]
        assert response.content_type == 'application/json'
        assert resp

    #@nottest
    def test_e_cleanup(self):
        """Clean up the database after /rememberedforms tests."""

        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = {'test.authentication.role': u'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), extra_environ=extra_environ)