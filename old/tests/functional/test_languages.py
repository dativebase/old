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
import os
import webtest
import simplejson as json
from nose.tools import nottest
from base64 import encodestring
from paste.deploy import appconfig
from sqlalchemy.sql import desc
from old.tests import *
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder

log = logging.getLogger(__name__)

def addSEARCHToWebTestValidMethods():
    new_valid_methods = list(webtest.lint.valid_methods)
    new_valid_methods.append('SEARCH')
    new_valid_methods = tuple(new_valid_methods)
    webtest.lint.valid_methods = new_valid_methods

class TestLanguagesController(TestController):

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    def tearDown(self):
        # Clear all models in the database except Language; recreate the users.
        pass

    #@nottest
    def test_index(self):
        """Tests that GET & SEARCH /languages behave correctly.
        
        NOTE: during testing, the language table contains only 8 records.
        """

        languages = Session.query(model.Language).all()

        # GET the languages
        response = self.app.get(url('languages'), headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == len(languages)
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 2, 'page': 2}
        response = self.app.get(url('languages'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 2
        assert resp['items'][0]['Part2B'] == languages[2].Part2B
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Language', 'orderByAttribute': 'Ref_Name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('languages'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted(languages, key=lambda l: l.Ref_Name, reverse=True)
        assert [l['Id'] for l in resp] == [l.Id for l in resultSet]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Language', 'orderByAttribute': 'Ref_Name',
                     'orderByDirection': 'desc', 'itemsPerPage': 1, 'page': 3}
        response = self.app.get(url('languages'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resultSet[2].Ref_Name == resp['items'][0]['Ref_Name']
        assert response.content_type == 'application/json'

        # Now test the show action:

        response = self.app.get(url('language', id=languages[4].Id),
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['Ref_Name'] == languages[4].Ref_Name
        assert response.content_type == 'application/json'

        # A nonexistent language Id will return a 404 error
        response = self.app.get(url('language', id=100987),
            headers=self.json_headers, extra_environ=self.extra_environ_view, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no language with Id 100987'
        assert response.content_type == 'application/json'

        # Test the search action
        addSEARCHToWebTestValidMethods()

        # A search on language transcriptions using POST /languages/search
        jsonQuery = json.dumps({'query': {'filter':
                        ['Language', 'Ref_Name', 'like', u'%m%']}})
        response = self.app.post(url('/languages/search'), jsonQuery,
                        self.json_headers, self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = [l for l in languages if u'm' in l.Ref_Name]
        assert resp
        assert set([l['Id'] for l in resp]) == set([l.Id for l in resultSet])
        assert response.content_type == 'application/json'

        # A search on language Ref_Name using SEARCH /languages
        jsonQuery = json.dumps({'query': {'filter':
                        ['Language', 'Ref_Name', 'like', u'%l%']}})
        response = self.app.request(url('languages'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = [l for l in languages if u'l' in l.Ref_Name]
        assert resp
        assert len(resp) == len(resultSet)
        assert set([l['Id'] for l in resp]) == set([l.Id for l in resultSet])

        # I'm just going to assume that the order by and pagination functions are
        # working correctly since the implementation is essentially equivalent
        # to that in the index action already tested above.

        # Attempting to call edit/new/create/delete/update on a read-only resource
        # will return a 404 response
        response = self.app.get(url('edit_language', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'
        response = self.app.get(url('new_language', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'
        response = self.app.post(url('languages'), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'
        response = self.app.put(url('language', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'
        response = self.app.delete(url('language', id=2232), status=404)
        assert json.loads(response.body)['error'] == u'This resource is read-only.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_new_search(self):
        """Tests that GET /languages/new_search returns the search parameters for searching the languages resource."""
        queryBuilder = SQLAQueryBuilder('Language')
        response = self.app.get(url('/languages/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['searchParameters'] == h.getSearchParameters(queryBuilder)
