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
from onlinelinguisticdatabase.model import FormSearch
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

todayTimestamp = datetime.datetime.now()
dayDelta = datetime.timedelta(1)
yesterdayTimestamp = todayTimestamp - dayDelta

def createTestFormSearches(n=100):
    """Create n form searches with various properties.  A testing ground for searches!
    """
    users = h.getUsers()
    viewer = [u for u in users if u.role == u'viewer'][0]
    contributor = [u for u in users if u.role == u'contributor'][0]
    administrator = [u for u in users if u.role == u'administrator'][0]

    for i in range(1, n + 1):
        fs = model.FormSearch()

        fs.enterer = contributor.id
        fs.search = unicode(json.dumps(
                {'query': {'filter': ['Form', 'transcription', 'regex', '%d' % i]}}))
        # name, description, search, searcher, datetimeModified
        if i % 2 == 0:
            fs.name = u'Form Search %d' % i
        else:
            fs.name = u'form search %d' % i

        if i > 50:
            fs.description = u'I really like this search and my favourite number is %d' % i

        if i > 20:
            fs.datetimeModified = todayTimestamp
        else:
            fs.datetimeModified = yesterdayTimestamp

        Session.add(fs)
    Session.commit()

def createTestData(n=100):
    createTestFormSearches(n)

def addSEARCHToWebTestValidMethods():
    new_valid_methods = list(webtest.lint.valid_methods)
    new_valid_methods.append('SEARCH')
    new_valid_methods = tuple(new_valid_methods)
    webtest.lint.valid_methods = new_valid_methods


class TestFormsearchesController(TestController):

    createParams = {
        'name': u'',
        'search': u'',
        'description': u'',
        'searcher': u''
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
        """Tests that GET /formsearches returns an array of all form searches and that orderBy and pagination parameters work correctly."""

        # Add 100 form searches.
        def createFormSearchFromIndex(index):
            formSearch = model.FormSearch()
            formSearch.name = u'formSearch%d' % index
            formSearch.description = u'description %d' % index
            formSearch.search = unicode(json.dumps(
                {'query': {'filter': ['Form', 'transcription', 'regex', '%d' % index]}}))
            return formSearch
        formSearches = [createFormSearchFromIndex(i) for i in range(1, 101)]
        Session.add_all(formSearches)
        Session.commit()
        formSearches = h.getFormSearches(True)
        formSearchesCount = len(formSearches)

        # Test that GET /formsearches gives us all of the form searches.
        response = self.app.get(url('formsearches'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == formSearchesCount
        assert resp[0]['name'] == u'formSearch1'
        assert resp[0]['id'] == formSearches[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('formsearches'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == formSearches[46].name

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'FormSearch', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('formsearches'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted([t.name for t in formSearches], reverse=True)
        assert resultSet == [t['name'] for t in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'FormSearch', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('formsearches'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['name']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'FormSearch', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('formsearches'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'FormSearchist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('formsearches'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == formSearches[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('formsearches'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('formsearches'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

    @nottest
    def test_create(self):
        """Tests that POST /formsearches creates a new formSearch
        or returns an appropriate error if the input is invalid.
        """

        originalFormSearchCount = Session.query(FormSearch).count()
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}

        # Create a valid one
        params = self.createParams.copy()
        params.update({
            'name': u'form search',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newFormSearchCount = Session.query(FormSearch).count()
        assert newFormSearchCount == originalFormSearchCount + 1
        assert resp['name'] == u'form search'
        assert resp['description'] == u"This one's worth saving!"
        assert json.loads(resp['search']) == query
        assert response.content_type == 'application/json'

        # Invalid because name is not unique
        params = self.createParams.copy()
        params.update({
            'name': u'form search',
            'description': u'Another one worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'The submitted value for FormSearch.name is not unique.'
        assert response.content_type == 'application/json'

        # Invalid because name is empty
        params = self.createParams.copy()
        params.update({
            'name': u'',
            'description': u'Another one worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'

        # Invalid because name is too long
        params = self.createParams.copy()
        params.update({
            'name': u'form search' * 300,
            'description': u'Another one worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

        # Invalid because search is invalid
        query = {'filter': ['Form', 'bar', 'like', '%m%']}
        params = self.createParams.copy()
        params.update({
            'name': u'invalid query',
            'description': u'Another one worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['search'] == u'The submitted query was invalid'

        # Another invalid search
        query = {'filter': ['Form', 'files', 'like', '%m%']}
        params = self.createParams.copy()
        params.update({
            'name': u'invalid query again',
            'description': u'Yet another one worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['search'] == u'The submitted query was invalid'

    @nottest
    def test_new(self):
        """Tests that GET /formsearches/new returns the data necessary to create a new form search."""
        response = self.app.get(url('new_formsearch'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert 'attributes' in resp['searchParameters']
        assert 'relations' in resp['searchParameters']
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /formsearches/id updates the form search with id=id."""

        # Create a form search to update.
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
        params = self.createParams.copy()
        params.update({
            'name': u'form search',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        formSearchCount = Session.query(FormSearch).count()
        formSearchId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'form search'
        assert resp['description'] == u"This one's worth saving!"
        assert json.loads(resp['search']) == query

        # Update the form search
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'name': u'form search for keeping',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.put(url('formsearch', id=formSearchId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newFormSearchCount = Session.query(FormSearch).count()
        assert formSearchCount == newFormSearchCount
        assert datetimeModified != originalDatetimeModified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('formsearch', id=formSearchId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        formSearchCount = newFormSearchCount
        newFormSearchCount = Session.query(FormSearch).count()
        ourFormSearchDatetimeModified = Session.query(FormSearch).get(formSearchId).datetimeModified
        assert ourFormSearchDatetimeModified.isoformat() == datetimeModified
        assert formSearchCount == newFormSearchCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /formsearches/id deletes the form search with id=id."""

        # Create a form search to delete.
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
        params = self.createParams.copy()
        params.update({
            'name': u'form search',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        formSearchCount = Session.query(FormSearch).count()
        formSearchId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'form search'
        assert resp['description'] == u"This one's worth saving!"
        assert json.loads(resp['search']) == query

        # Now delete the formSearch
        response = self.app.delete(url('formsearch', id=formSearchId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newFormSearchCount = Session.query(FormSearch).count()
        assert newFormSearchCount == formSearchCount - 1
        assert resp['id'] == formSearchId
        assert response.content_type == 'application/json'

        # Trying to get the deleted formSearch from the db should return None
        deletedFormSearch = Session.query(FormSearch).get(formSearchId)
        assert deletedFormSearch == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('formsearch', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no form search with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('formsearch', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

    @nottest
    def test_show(self):
        """Tests that GET /formsearches/id returns the formsearch with id=id or an appropriate error."""

        # Create a form search to show.
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
        params = self.createParams.copy()
        params.update({
            'name': u'form search',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        formSearchCount = Session.query(FormSearch).count()
        formSearchId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'form search'
        assert resp['description'] == u"This one's worth saving!"
        assert json.loads(resp['search']) == query

        # Try to get a form search using an invalid id
        id = 100000000000
        response = self.app.get(url('formsearch', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert u'There is no form search with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('formsearch', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

        # Valid id
        response = self.app.get(url('formsearch', id=formSearchId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'form search'
        assert resp['description'] == u"This one's worth saving!"
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /formsearches/id/edit returns a JSON object of data necessary to edit the form search with id=id.

        The JSON object is of the form {'formSearch': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a form search to edit.
        query = {'filter': ['Form', 'transcription', 'regex', u'[a-g]{3,}']}
        params = self.createParams.copy()
        params.update({
            'name': u'form search',
            'description': u'This one\'s worth saving!',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        formSearchCount = Session.query(FormSearch).count()
        formSearchId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert resp['name'] == u'form search'
        assert resp['description'] == u"This one's worth saving!"
        assert json.loads(resp['search']) == query

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_formsearch', id=formSearchId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_formsearch', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no form search with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_formsearch', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_formsearch', id=formSearchId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['formSearch']['name'] == u'form search'
        assert 'attributes' in resp['data']['searchParameters']
        assert 'relations' in resp['data']['searchParameters']
        assert response.content_type == 'application/json'

    @nottest
    def test_search(self):
        """Tests that SEARCH /formsearches (a.k.a. POST /formsearches/search) correctly returns an array of formsearches based on search criteria."""

        # Create some formSearches (and other models) to search and add SEARCH to the list of allowable methods
        createTestData(100)
        addSEARCHToWebTestValidMethods()

        formSearches = json.loads(json.dumps(h.getFormSearches(True), cls=h.JSONOLDEncoder))

        # Searching where values may be NULL
        jsonQuery = json.dumps({'query': {'filter': ['FormSearch', 'search', 'like', '%2%']}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [fs for fs in formSearches if u'2' in fs['search']]
        assert resp
        assert len(resp) == len(resultSet)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in resultSet])
        assert response.content_type == 'application/json'

        # A fairly complex search
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['FormSearch', 'name', 'regex', '[13456]'],
                ['not', ['FormSearch', 'name', 'like', u'%F%']],
                ['or', [
                    ['FormSearch', 'search', 'regex', u'[1456]'],
                    ['FormSearch', 'datetimeModified', '>', yesterdayTimestamp.isoformat()]]]]]}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [fs for fs in formSearches if
            re.search('[13456]', fs['name']) and not 'F' in fs['name'] and
            (re.search('[1456]', fs['search']) or fs['datetimeModified'] > yesterdayTimestamp.isoformat())]
        assert resp
        assert len(resp) == len(resultSet)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in resultSet])

        # A basic search with a paginator provided.
        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'search', 'like', '%3%']},
            'paginator': {'page': 2, 'itemsPerPage': 5}})
        response = self.app.request(url('formsearches'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [fs for fs in formSearches if fs['search'] and '3' in fs['search']]
        assert resp['paginator']['count'] == len(resultSet)
        assert len(resp['items']) == 5
        assert resp['items'][0]['id'] == resultSet[5]['id']
        assert resp['items'][-1]['id'] == resultSet[9]['id']

        # An invalid paginator (here 'page' is less than 1) will result in formencode.Invalid
        # being raised resulting in a response with a 400 status code and a JSON error msg.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['FormSearch', 'search', 'like', '%3%']},
            'paginator': {'page': 0, 'itemsPerPage': 10}})
        response = self.app.request(url('formsearches'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

        # Some "invalid" paginators will silently fail.  For example, if there is
        # no 'pages' key, then SEARCH /formsearches will just assume there is no paginator
        # and all of the results will be returned.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['FormSearch', 'search', 'like', '%3%']},
            'paginator': {'pages': 1, 'itemsPerPage': 10}})
        response = self.app.request(url('formsearches'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len([fs for fs in formSearches if s['search'] and '3' in fs['search']])

        # Adding a 'count' key to the paginator object in the request will spare
        # the server from running query.count().  Note that the server will not
        # attempt to verify the count (since that would defeat the purpose) but
        # will simply pass it back.  The server trusts that the client is passing
        # in a factual count.  Here we pass in an inaccurate count for demonstration.
        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'search', 'like', '%3%']},
            'paginator': {'page': 2, 'itemsPerPage': 4, 'count': 750}})
        response = self.app.request(url('formsearches'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['paginator']['count'] == 750
        assert len(resp['items']) == 4
        assert resp['items'][0]['id'] == resultSet[4]['id']
        assert resp['items'][-1]['id'] == resultSet[7]['id']

        # Test order by: order by name descending
        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'search', 'regex', '.'],
                'orderBy': ['FormSearch', 'name', 'desc']}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = sorted(formSearches, key=lambda fs: fs['name'].lower(), reverse=True)
        assert len(resp) == 100
        rsIds = [fs['id'] for fs in resultSet]
        rsNames = [fs['name'] for fs in resultSet]
        rIds = [fs['id'] for fs in resp]
        rNames = [fs['name'] for fs in resp]
        assert rsNames == rNames
        assert resp[0]['name'] == u'form search 99'
        assert resp[-1]['name'] == u'form search 1'

        # order by with missing direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'search', 'regex', '.'],
                'orderBy': ['FormSearch', 'name']}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['name'] == u'form search 1'
        assert resp[-1]['name'] == u'form search 99'
        assert response.content_type == 'application/json'

        # order by with unknown direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'search', 'regex', '.'],
                'orderBy': ['FormSearch', 'name', 'descending']}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['name'] == u'form search 1'
        assert resp[-1]['name'] == u'form search 99'

        # syntactically malformed order by
        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'search', 'regex', '.'],
                'orderBy': ['FormSearch']}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'
        assert response.content_type == 'application/json'

        # searches with lexically malformed order bys
        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'name', 'regex', '.'],
                'orderBy': ['FormSearch', 'foo', 'desc']}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['FormSearch.foo'] == u'Searching on FormSearch.foo is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        jsonQuery = json.dumps({'query': {
                'filter': ['FormSearch', 'name', 'regex', '.'],
                'orderBy': ['Foo', 'id', 'desc']}})
        response = self.app.post(url('/formsearches/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Foo'] == u'Searching the FormSearch model by joining on the Foo model is not possible'
        assert resp['errors']['Foo.id'] == u'Searching on Foo.id is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

    @nottest
    def test_new_search(self):
        """Tests that GET /formsearches/new_search returns the search parameters for searching the form searches resource."""
        queryBuilder = SQLAQueryBuilder('FormSearch')
        response = self.app.get(url('/formsearches/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['searchParameters'] == h.getSearchParameters(queryBuilder)
