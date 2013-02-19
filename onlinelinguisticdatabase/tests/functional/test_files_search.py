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

"""This module tests the file search functionality, i.e., requests to SEARCH
/files and POST /files/search.

NOTE: getting the non-standard http SEARCH method to work in the tests required
using the request method of TestController().app and specifying values for the
method, body, headers, and environ kwarg parameters.  WebTest prints a
WSGIWarning when unknown HTTP methods (e.g., SEARCH) are used.  To prevent this,
I altered the global valid_methods tuple of webtest.lint at runtime by adding a
'SEARCH' method (see addSEARCHToWebTestValidMethods() below).
"""

import re, os
from base64 import encodestring
from onlinelinguisticdatabase.tests import *
from nose.tools import nottest
import simplejson as json
import logging
from datetime import date, datetime, timedelta
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
import webtest
from paste.deploy import appconfig

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

def isofy(date):
    try:
        return date.isoformat()
    except AttributeError:
        return date

################################################################################
# Functions for creating & retrieving test data
################################################################################


def addSEARCHToWebTestValidMethods():
    new_valid_methods = list(webtest.lint.valid_methods)
    new_valid_methods.append('SEARCH')
    new_valid_methods = tuple(new_valid_methods)
    webtest.lint.valid_methods = new_valid_methods


class TestFormsSearchController(TestController):

    here = appconfig('config:test.ini', relative_to='.')['here']
    filesPath = os.path.join(here, 'files')
    testFilesPath = os.path.join(here, 'test_files')

    createParams = {
        'name': u'',
        'description': u'',
        'dateElicited': u'',    # mm/dd/yyyy
        'elicitor': u'',
        'speaker': u'',
        'utteranceType': u'',
        'embeddedFileMarkup': u'',
        'embeddedFilePassword': u'',
        'tags': [],
        'file': ''      # file data Base64 encoded
    }

    def _createTestModels(self, n=20):
        self._addTestModelsToSession('Tag', n, ['name'])
        self._addTestModelsToSession('Speaker', n, ['firstName', 'lastName', 'dialect'])
        self._addTestModelsToSession('Form', n, ['transcription', 'datetimeEntered', 'datetimeModified'])
        Session.commit()

    def _addTestModelsToSession(self, modelName, n, attrs):
        for i in range(1, n + 1):
            m = getattr(model, modelName)()
            for attr in attrs:
                if attr in ('datetimeModified, datetimeEntered'):
                    setattr(m, attr, datetime.now())
                else:
                    setattr(m, attr, u'%s %s' % (attr, i))
            Session.add(m)

    def _getTestModels(self):
        defaultModels = {
            'tags': [t.__dict__ for t in h.getTags()],
            'forms': [f.__dict__ for f in h.getForms()],
            'speakers': [s.__dict__ for s in h.getSpeakers()],
            'users': [u.__dict__ for u in h.getUsers()]
        }
        return defaultModels

    def _createTestData(self, n=20):
        self._createTestModels(n)
        self._createTestFiles(n)

    def _createTestFiles(self, n=20):
        """Create n files with various properties.  A testing ground for searches!
        """
        testModels = self._getTestModels()
        viewer = [u for u in testModels['users'] if u['role'] == u'viewer'][0]
        contributor = [u for u in testModels['users'] if u['role'] == u'contributor'][0]
        administrator = [u for u in testModels['users'] if u['role'] == u'administrator'][0]
        ids = []
        for i in range(1, n + 1):
            jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
            jpgBase64 = encodestring(open(jpgFilePath).read())
            wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
            wavBase64 = encodestring(open(wavFilePath).read())
            params = self.createParams.copy()

            if i < 11:
                params.update({
                    'base64EncodedFile': jpgBase64,
                    'filename': u'name_%d.jpg' % i,
                    'name': u'name_%d.jpg' % i,
                    'tags': [testModels['tags'][i - 1]['id']]
                })
            elif i < 21:
                params.update({
                    'base64EncodedFile': jpgBase64,
                    'filename': u'Name_%d.jpg' % i,
                    'dateElicited': u'%02d/%02d/%d' % (jan1.month, jan1.day, jan1.year)
                })
            elif i < 31:
                params.update({
                    'base64EncodedFile': wavBase64,
                    'filename': u'Name_%d.wav' % i,
                    'dateElicited': u'%02d/%02d/%d' % (jan1.month, jan1.day, jan1.year)
                })
            elif i < 41:
                params.update({'parentFile': ids[-10], 'start': 1, 'end': 2,
                               'name': u'Name_%d' % i})
            else:
                params.update({'name': u'Name_%d' % i, 'MIMEtype': u'video/mpeg',
                               'url': 'http://vimeo.com/54144270'})

            if i in [36, 37]:
                del params['name']

            if i in [13, 15]:
                params.update({
                    'dateElicited': u'%02d/%02d/%d' % (jan3.month, jan3.day, jan3.year)
                })

            if i > 5 and i < 16:
                params.update({
                    'forms': [testModels['forms'][i - 1]['id']]
                })

            params = json.dumps(params)
            response = self.app.post(url('files'), params, self.json_headers,
                                     self.extra_environ_admin)
            resp = json.loads(response.body)
            ids.append(resp['id'])

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    extra_environ_viewer = {'test.authentication.role': u'viewer'}
    json_headers = {'Content-Type': 'application/json'}
    n = 50

    def tearDown(self):
        pass

    # Initialization for the tests - this needs to be run first in order for the
    # tests to succeed
    #@nottest
    def test_a_initialize(self):
        """Tests POST /files/search: initialize database."""
        # Add a bunch of data to the db.
        self._createTestData(self.n)
        addSEARCHToWebTestValidMethods()

    #@nottest
    def test_search_b_equals(self):
        """Tests POST /files/search: equals."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', '=', 'name_10.jpg']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['name'] == u'name_10.jpg'

    #@nottest
    def test_search_c_not_equals(self):
        """Tests SEARCH /files: not equals."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['File', 'name', '=', u'name_10.jpg']]}})
        response = self.app.request(url('files'), method='SEARCH',
            body=jsonQuery, headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == self.n - 1
        assert u'name_10.jpg' not in [f['name'] for f in resp]

    #@nottest
    def test_search_d_like(self):
        """Tests POST /files/search: like."""

        files = [f.getDict() for f in h.getFiles()]

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'like', u'%1%']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'1' in f['name']]
        assert len(resp) == len(resultSet)

        # Case-sensitive like.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'like', u'%N%']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'N' in f['name']]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['or', [
                ['File', 'name', 'like', u'N%'],
                ['File', 'name', 'like', u'n%']]]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'N' in f['name'] or u'n' in f['name']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_e_not_like(self):
        """Tests SEARCH /files: not like."""
        files = [f.getDict() for f in h.getFiles()]
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['File', 'name', 'like', u'%1%']]}})
        response = self.app.request(url('files'), method='SEARCH',
            body=jsonQuery, headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'1' not in f['name']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_f_regexp(self):
        """Tests POST /files/search: regular expression."""
        files = [f.getDict() for f in h.getFiles()]

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'[345]2']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if re.search('[345]2', f['name'])]
        assert sorted([f['name'] for f in resp]) == sorted([f['name'] for f in resultSet])
        assert len(resp) == len(resultSet)

        # Case-sensitive regexp.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'^N']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['name'][0] == u'N']
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'^[Nn]']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['name'][0] in [u'N', 'n']]
        assert len(resp) == len(resultSet)

        # Beginning and end of string anchors
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'^[Nn]ame_1.jpg$']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['name'] in [u'Name_1.jpg', u'name_1.jpg']]
        assert len(resp) == len(resultSet)

        # Quantifiers
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'1{1,}']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if re.search('1{1,}', f['name'])]
        assert len(resp) == len(resultSet)

        # Quantifiers
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'[123]{2,}']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if re.search('[123]{2,}', f['name'])]
        assert len(resp) == len(resultSet)

        # Bad regex
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'[123]{3,2}']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    #@nottest
    def test_search_g_not_regexp(self):
        """Tests SEARCH /files: not regular expression."""
        files = [f.getDict() for f in h.getFiles()]
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['File', 'name', 'regexp', u'[345]2']]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if not re.search('[345]2', f['name'])]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_h_empty(self):
        """Tests POST /files/search: is NULL."""
        files = [f.getDict() for f in h.getFiles()]

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'description', '=', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['description'] is None]
        assert len(resp) == len(resultSet)

        # Same as above but with a double negative
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['File', 'description', '!=', None]]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_i_not_empty(self):
        """Tests SEARCH /files: is not NULL."""
        files = [f.getDict() for f in h.getFiles()]
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['File', 'description', '=', None]]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['description'] is not None]
        assert len(resp) == len(resultSet)

        # Same as above, but with !=, i.e., __ne__
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'description', '!=', None]}})
        response = self.app.request(url('files'), body=jsonQuery, method='SEARCH',
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_j_invalid_json(self):
        """Tests POST /files/search: invalid JSON params."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['File', 'description', '=', None]]}})
        jsonQuery = jsonQuery[:-1]  # Cut off the end to make it bad!
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'JSON decode error: the parameters provided were not valid JSON.'

    #@nottest
    def test_search_k_malformed_query(self):
        """Tests SEARCH /files: malformed query."""

        files = [f.getDict() for f in h.getFiles()]

        # TypeError - bad num args: 'NOT' will be treated as the first arg to
        # _getSimpleFilterExpression and ['File', 'name', '=', 10] will be passed
        # as the second -- two more are required.
        jsonQuery = json.dumps({'query': {'filter': ['NOT', ['File', 'id', '=', 10]]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # After recognizing 'not', the query builder will look at only the next
        # list and ignore all the rest.
        jsonQuery = json.dumps(
            {'query': {'filter':
                ['not',
                    ['File', 'name', '=', 'name_10.jpg'], 
                    ['File', 'name', '=', 'name_10.jpg'],
                    ['File', 'name', '=', 'name_10.jpg']]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['name'] != u'name_10.jpg']
        assert len(resp) == len(resultSet)
        assert 'name 10' not in [f['name'] for f in resp]

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps({'query': {'filter': ['not']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[0] is called.
        jsonQuery = json.dumps({'query': {'filter': []}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps({'query': {'filter': ['and']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['IndexError'] == u'list index out of range'

        # TypeError bad num args will be triggered when _getSimpleFilterExpression is
        # called on a string whose len is not 4, i.e., 'id' or '='.
        jsonQuery = json.dumps({'query': {'filter': ['and', ['File', 'id', '=', '1099']]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'TypeError' in resp['errors']
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # TypeError when asking whether [] is in a dict (lists are unhashable)
        jsonQuery = json.dumps({'query': {'filter': [[], 'a', 'a', 'a']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['TypeError'] == u"unhashable type: 'list'"
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # With no 'query' attribute, the SQLAQueryBuilder will be passed None and
        # will immediately raise an AttributeError.
        jsonQuery = json.dumps({'filter': ['File', 'id', '=', 2]})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

        # With no 'filter' attribute, the SQLAQueryBuilder will be passed a list
        # will immediately raise an AttributeError when it tries to call [...].get('filter').
        jsonQuery = json.dumps({'query': ['File', 'id', '=', 2]})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    #@nottest
    def test_search_l_lexical_semantic_error(self):
        """Tests POST /files/search: lexical & semantic errors.

        These are when SQLAQueryBuilder.py raises a OLDSearchParseError because a
        relation is not permitted, e.g., 'contains', or not permitted for a
        given attribute.
        """

        # searchParser.py does not allow the contains relation (OLDSearchParseError)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'name', 'contains', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'File.name.contains' in resp['errors']

        # model.File.tags.__eq__('abcdefg') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'tags', '=', u'abcdefg']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

        # model.File.tags.regexp('xyz') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['File', 'tags', 'regex', u'xyz']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['File.tags.regex'] == u'The relation regex is not permitted for File.tags'

        # model.File.tags.like('name') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['File', 'tags', 'like', u'abc']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.tags.like'] == \
            u'The relation like is not permitted for File.tags'

        # model.File.tags.__eq__('tag') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['File', 'tags', '__eq__', u'tag']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'InvalidRequestError' in resp['errors']

    #@nottest
    def test_search_m_conjunction(self):
        """Tests SEARCH /files: conjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]
        models = self._getTestModels()
        files = [f.getDict() for f in h.getFiles()]

        # 1 conjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'and', [
                ['File', 'name', 'like', u'%2%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'2' in f['name']]
        assert len(resp) == len(resultSet)

        # 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['File', 'name', 'like', u'%2%'],
                ['File', 'name', 'like', u'%1%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'2' in f['name'] and u'1' in f['name']]
        assert len(resp) == len(resultSet)
        assert sorted([f['name'] for f in resp]) == sorted([f['name'] for f in resultSet])

        # More than 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['File', 'name', 'like', u'%1%'],
                ['File', 'elicitor', 'id', '=', contributor.id],
                ['File', 'speaker', 'id', '=', models['speakers'][3]['id']]
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'1' in f['name'] and
                     (f['elicitor'] and f['elicitor']['id'] == contributor.id) and
                     (f['speaker'] and f['speaker']['id'] == models['speakers'][3]['id'])]
        assert len(resp) == len(resultSet)
        assert sorted([f['name'] for f in resp]) == sorted([f['name'] for f in resultSet])

        # Multiple redundant conjuncts -- proof of possibility
        query = {'query': {'filter': [
            'and', [
                ['File', 'name', 'like', u'%1%'],
                ['File', 'name', 'like', u'%1%'],
                ['File', 'name', 'like', u'%1%'],
                ['File', 'name', 'like', u'%1%'],
                ['File', 'name', 'like', u'%1%'],
                ['File', 'name', 'like', u'%1%'],
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'1' in f['name']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_n_disjunction(self):
        """Tests POST /files/search: disjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]
        files = [f.getDict() for f in h.getFiles()]

        # 1 disjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'or', [
                ['File', 'name', 'like', u'%2%']   # 19 total
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'2' in f['name']]
        assert len(resp) == len(resultSet)

        # 2 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['File', 'name', 'like', u'%2%'],
                ['File', 'name', 'like', u'%1%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'2' in f['name'] or u'1' in f['name']]
        assert len(resp) == len(resultSet)

        # 3 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['File', 'name', 'like', u'%2%'],
                ['File', 'name', 'like', u'%1%'],
                ['File', 'elicitor', 'id', '=', contributor.id]
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if u'2' in f['name'] or u'1' in f['name']
                     or (f['elicitor'] and f['elicitor']['id'] == contributor.id)]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_o_int(self):
        """Tests SEARCH /files: integer searches."""

        files = [f.getDict() for f in h.getFiles()]
        fileIds = [f['id'] for f in files]

        # = int
        jsonQuery = json.dumps({'query': {'filter': ['File', 'id', '=', fileIds[1]]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['id'] == fileIds[1]

        # < int (str)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'id', '<', str(fileIds[16])]}}) # Thanks to SQLAlchemy, a string will work here too
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['id'] < fileIds[16]]
        assert len(resp) == len(resultSet)

        # >= int
        jsonQuery = json.dumps({'query': {'filter': ['File', 'id', '>=', fileIds[9]]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['id'] >= fileIds[9]]
        assert len(resp) == len(resultSet)

        # in array
        jsonQuery = json.dumps(
            {'query': {'filter':
                ['File', 'id', 'in', [fileIds[1], fileIds[3], fileIds[8], fileIds[19]]]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4
        assert sorted([f['id'] for f in resp]) == [fileIds[1], fileIds[3], fileIds[8], fileIds[19]]

        # in None -- Error
        jsonQuery = json.dumps({'query': {'filter': ['File', 'id', 'in', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.id.in_'] == u"Invalid filter expression: File.id.in_(None)"

        # in int -- Error
        jsonQuery = json.dumps({'query': {'filter': ['File', 'id', 'in', 2]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.id.in_'] == u"Invalid filter expression: File.id.in_(2)"

        # regex int - The OLD's Python-based regexp implementation for SQLite will
        # automatically convert a non-string field value to a string before doing
        # the regexp comparison.  I believe that this parallels MySQL's regexp
        # behaviour accurately.
        strPatt = u'[12][12]'
        patt = re.compile(strPatt)
        expectedIdMatches = [f['id'] for f in files if patt.search(str(f['id']))]
        jsonQuery = json.dumps({'query': {'filter': ['File', 'id', 'regex', strPatt]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedIdMatches)
        assert sorted([f['id'] for f in resp]) == sorted(expectedIdMatches)

        # like int - RDBMS treats ints as strings for LIKE search
        jsonQuery = json.dumps({'query': {'filter': ['File', 'id', 'like', u'%2%']}})
        expectedMatches = [i for i in fileIds if u'2' in str(i)]
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedMatches)

    #@nottest
    def test_search_p_date(self):
        """Tests POST /files/search: date searches."""
        files = [f.getDict() for f in h.getFiles()]

        # = date
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '=', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if isofy(f['dateElicited']) == jan1.isoformat()]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '=', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if isofy(f['dateElicited']) == jan3.isoformat()]
        assert len(resp) == len(resultSet)

        # != date -- *NOTE:* the NULL dateElicited values will not be counted.
        # The implicit query is 'is not null and != 2012-01-01'
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '!=', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if isofy(f['dateElicited']) is not None and
                     isofy(f['dateElicited']) != jan1.isoformat()]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '!=', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if isofy(f['dateElicited']) is not None and
                     isofy(f['dateElicited']) != jan3.isoformat()]
        assert len(resp) == len(resultSet)

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter': [
            'or', [['File', 'dateElicited', '!=', jan1.isoformat()],
                ['File', 'dateElicited', '=', None]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if isofy(f['dateElicited']) != jan1.isoformat()]
        assert len(resp) == len(resultSet)

        # < date
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '<', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and f['dateElicited'] < jan1]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '<', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and f['dateElicited'] < jan3]
        assert len(resp) == len(resultSet)

        # <= date
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '<=', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and f['dateElicited'] <= jan3]
        assert len(resp) == len(resultSet)

        # > date
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '>', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and f['dateElicited'] > jan2]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '>', '0001-01-01']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and
                     isofy(f['dateElicited']) > '0001-01-01']
        assert len(resp) == len(resultSet)

        # >= date
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '>=', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and f['dateElicited'] >= jan1]
        assert len(resp) == len(resultSet)

        # =/!= None
        jsonQuery = json.dumps({'query': {'filter': ['File', 'dateElicited', '=', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is None]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '__ne__', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_q_date_invalid(self):
        """Tests SEARCH /files: invalid date searches."""

        files = [f.getDict() for f in h.getFiles()]

        # = invalid date
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '=', '12-01-01']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 12-01-01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', '=', '2012-01-32']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 2012-01-32'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on invalid date will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', 'regex', '01']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on valid date will work and will act just like = -- no point
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', 'regex', '2012-01-01']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and
                     f['dateElicited'].isoformat() == '2012-01-01']
        assert len(resp) == len(resultSet)

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', 'like', '2012-01-01']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet)

        # in_ on a date.  This will raise a TypeError ('datetime.date' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', 'in', '2012-01-02']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.dateElicited.in_'] == u'Invalid filter expression: File.dateElicited.in_(datetime.date(2012, 1, 2))'

        # in_ on a list of dates works (SQLAQueryBuilder generates a list of date objects)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'dateElicited', 'in', ['2012-01-01', '2012-01-03']]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['dateElicited'] is not None and
                     f['dateElicited'].isoformat() in ['2012-01-01', '2012-01-03']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_r_datetime(self):
        """Tests POST /files/search: datetime searches."""
        files = [f.getDict() for f in h.getFiles()]

        # = datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] == todayTimestamp]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] == yesterdayTimestamp]
        assert len(resp) == len(resultSet)

        # != datetime -- *NOTE:* the NULL datetimeEntered values will not be counted.
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '!=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] != todayTimestamp]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '!=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] != yesterdayTimestamp]
        assert len(resp) == len(resultSet)

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter':
            ['or', [['File', 'datetimeEntered', '!=', todayTimestamp.isoformat()],
                ['File', 'datetimeEntered', '=', None]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is None or
                     f['datetimeEntered'] != todayTimestamp]
        assert len(resp) == len(resultSet)

        # < datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '<', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'] < todayTimestamp]
        assert len(resp) == len(resultSet)

        # <= datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '<=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'] <= todayTimestamp]
        assert len(resp) == len(resultSet)

        # > datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '>', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'] > todayTimestamp]
        assert len(resp) == len(resultSet)
        # Note: Python2.6/Debian(?) bug: using a year before 1900 will cause problems: 
        # ValueError: year=1 is before 1900; the datetime strftime() methods require year >= 1900
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '>', '1901-01-01T09:08:07']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'].isoformat() > '1901-01-01T09:08:07']
        assert len(resp) == len(resultSet)

        # >= datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '>=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'] >= yesterdayTimestamp]
        assert len(resp) == len(resultSet)

        # =/!= None
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '=', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is None]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeEntered', '__ne__', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None]
        assert len(resp) == len(resultSet)

        # datetime in today
        midnightToday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        midnightTomorrow = midnightToday + dayDelta
        query = {'query': {'filter':
            ['and', [['File', 'datetimeEntered', '>', midnightToday.isoformat()],
                         ['File', 'datetimeEntered', '<', midnightTomorrow.isoformat()]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'] > midnightToday and
                     f['datetimeEntered'] < midnightTomorrow]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_s_datetime_invalid(self):
        """Tests SEARCH /files: invalid datetime searches."""
        files = [f.getDict() for f in h.getFiles()]

        # = invalid datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeModified', '=', '12-01-01T09']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 12-01-01T09'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeModified', '=', '2012-01-30T09:08:61']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 2012-01-30T09:08:61'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # Trailing period and too many microseconds will both succeed.
        jsonQuery = json.dumps({'query': {'filter':
                ['File', 'datetimeModified', '=', '2012-01-30T09:08:59.123456789123456789123456789']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'datetimeModified', '=', '2012-01-30T09:08:59.']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)

        # regex on invalid datetime will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'datetimeModified', 'regex', '01']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 01'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # regex on valid datetime will work and will act just like = -- no point
        jsonQuery = json.dumps({'query': {'filter':
                ['File', 'datetimeEntered', 'regex', todayTimestamp.isoformat()]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'] == todayTimestamp]
        assert len(resp) == len(resultSet)

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps({'query': {'filter':
                ['File', 'datetimeModified', 'like', todayTimestamp.isoformat()]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeEntered'] is not None and
                     f['datetimeEntered'] == todayTimestamp]
        assert len(resp) == len(resultSet)

        # in_ on a datetime.  This will raise a TypeError ('datetime.datetime' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'datetimeModified', 'in', todayTimestamp.isoformat()]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.datetimeModified.in_'] == \
            u'Invalid filter expression: File.datetimeModified.in_(%s)' % repr(todayTimestamp)

        # in_ on a list of datetimes works (SQLAQueryBuilder generates a list of datetime objects)
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'datetimeModified', 'in',
                [todayTimestamp.isoformat(), yesterdayTimestamp.isoformat()]]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['datetimeModified'] is not None and
                     f['datetimeModified'] in (todayTimestamp, yesterdayTimestamp)]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_t_many_to_one(self):
        """Tests POST /files/search: searches on many-to-one attributes."""
        files = [f.getDict() for f in h.getFiles()]

        testModels = self._getTestModels()
        users = h.getUsers()
        forms = h.getForms()
        viewer = [u for u in users if u.role == u'viewer'][0]
        contributor = [u for u in users if u.role == u'contributor'][0]
        administrator = [u for u in users if u.role == u'administrator'][0]

        # = int
        jsonQuery = json.dumps(
            {'query': {'filter': ['File', 'enterer', 'id', '=', contributor.id]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['enterer']['id'] == contributor.id]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', '=', testModels['speakers'][0]['id']]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['speaker'] and
                     f['speaker']['id'] == testModels['speakers'][0]['id']]
        assert len(resp) == len(resultSet)

        # in array of ints
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'in', [s['id'] for s in testModels['speakers']]]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['speaker'] and
                     f['speaker']['id'] in [s['id'] for s in testModels['speakers']]]
        assert len(resp) == len(resultSet)

        # <
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', '<', 15]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['speaker'] and
                     f['speaker']['id'] < 15]
        assert len(resp) == len(resultSet)

        # regex
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'regex', '5']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['speaker'] and
                     u'5' in str(f['speaker']['id'])]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'regex', '[56]']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['speaker'] and
                     re.search('[56]', str(f['speaker']['id']))]
        assert len(resp) == len(resultSet)

        # like
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'like', '%5%']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['speaker'] and
                     '5' in str(f['speaker']['id'])]
        assert len(resp) == len(resultSet)

        # regex on parentFile.filename
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'parentFile', 'filename', 'regex', '[13579]']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['parentFile'] and
                     set(list('13579')) & set(list(f['parentFile']['filename']))]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_v_many_to_many(self):
        """Tests POST /files/search: searches on many-to-many attributes, i.e., Tag, Form."""
        files = [f.getDict() for f in h.getFiles()]

        # tag.name =
        jsonQuery = json.dumps({'query': {'filter': ['Tag', 'name', '=', 'name_6.jpg']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if 'name_6.jpg' in [t['name'] for t in f['tags']]]
        assert len(resp) == len(resultSet)

        # tag.name = (using any())
        jsonQuery = json.dumps({'query': {'filter': ['File', 'tags', 'name', '=', 'name_6.jpg']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet)

        # form.transcription like
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'like', '%transcription 6%']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files
                     if 'transcription 6' in ''.join([fo['transcription'] for fo in f['forms']])]
        assert len(resp) == len(resultSet)

        # form.transcription regexp
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'regex', 'transcription [12]']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files
                     if re.search('transcription [12]', ''.join([fo['transcription'] for fo in f['forms']]))]
        assert len(resp) == len(resultSet)

        # tag.name in_
        names = [u'name 77', u'name 79', u'name 99']
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', 'in_', names]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if set(names) & set([t['name'] for t in f['tags']])]
        assert len(resp) == len(resultSet)

        # tag.name <
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', '<', u'name 2']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if [t for t in f['tags'] if t['name'] < u'name 2']]
        assert len(resp) == len(resultSet)

        # form.datetimeEntered
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'datetimeEntered', '>', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files
                     if [fo for fo in f['forms'] if fo['datetimeEntered'] > yesterdayTimestamp]]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'datetimeEntered', '<', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files
                     if [fo for fo in f['forms'] if fo['datetimeEntered'] < yesterdayTimestamp]]
        assert len(resp) == len(resultSet)

        # To search for the presence/absence of tags/forms, one must use the
        # tags/forms attributes of the File model.
        jsonQuery = json.dumps({'query': {'filter': ['File', 'tags', '=', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if not f['tags']]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps({'query': {'filter': ['File', 'forms', '!=', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['forms']]
        assert len(resp) == len(resultSet)

        # Using anything other than =/!= on Form.tags/files/collections will raise an error.
        jsonQuery = json.dumps({'query': {'filter': ['File', 'tags', 'like', None]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.tags.like'] == u'The relation like is not permitted for File.tags'

        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'forms', '=', 'form 2']}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

    #@nottest
    def test_search_w_in(self):
        """Tests SEARCH /files: searches using the in_ relation."""
        files = [f.getDict() for f in h.getFiles()]

        # Array value -- all good.
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'in', ['name_1.jpg']]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['name'] in ['name_1.jpg']]
        assert len(resp) == len(resultSet)

        # String value -- no error because strings are iterable; but no results
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'in', 'name_1.jpg']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0

    #@nottest
    def test_search_x_complex(self):
        """Tests POST /files/search: complex searches."""
        files = [f.getDict() for f in h.getFiles()]

        # A fairly complex search
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['Tag', 'name', 'like', '%1%'],
                ['not', ['File', 'name', 'regex', '[12][5-7]']],
                ['or', [
                    ['File', 'datetimeEntered', '>', todayTimestamp.isoformat()],
                    ['File', 'dateElicited', '>', jan1.isoformat()]]]]]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if
            '1' in ' '.join([t['name'] for t in f['tags']]) and
            not re.search('[12][5-7]', f['name']) and
            (todayTimestamp < f['datetimeEntered'] or
            (f['dateElicited'] and jan1 < f['dateElicited']))]
        assert len(resp) == len(resultSet)

        # A complex search entailing multiple joins
        tagNames = ['name 2', 'name 4', 'name 8']
        patt = '([13579][02468])|([02468][13579])'
        jsonQuery = json.dumps({'query': {'filter': [
            'or', [
                ['Form', 'transcription', 'like', '%1%'],
                ['Tag', 'name', 'in', tagNames],
                ['and', [
                    ['not', ['File', 'name', 'regex', patt]],
                    ['File', 'dateElicited', '!=', None]]]]]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if
            '1' in ' '.join([fo['transcription'] for fo in f['forms']]) or
            set([t['name'] for t in f['tags']]) & set(tagNames) or
            (not re.search(patt, f['name']) and
             f['dateElicited'] is not None)]
        assert len(resp) == len(resultSet)

        # A complex search ...  The implicit assertion is that a 200 status
        # code is returned.  At this point I am not going to bother attempting to
        # emulate this query in Python ...
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['File', 'name', 'like', '%5%'],
                ['File', 'description', 'regex', '.'],
                ['not', ['Tag', 'name', 'like', '%6%']],
                ['or', [
                    ['File', 'datetimeEntered', '<', todayTimestamp.isoformat()],
                    ['not', ['File', 'dateElicited', 'in', [jan1.isoformat(), jan3.isoformat()]]],
                    ['and', [
                        ['File', 'enterer', 'id', 'regex', '[135680]'],
                        ['File', 'id', '<', 90]
                    ]]
                ]],
                ['not', ['not', ['not', ['Tag', 'name', '=', 'name 7']]]]
            ]
        ]}})
        response = self.app.post(url('/files/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

    #@nottest
    def test_search_y_paginator(self):
        """Tests SEARCH /files: paginator."""
        files = json.loads(json.dumps(h.getFiles(), cls=h.JSONOLDEncoder))

        # A basic search with a paginator provided.
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'page': 2, 'itemsPerPage': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if 'N' in f['name']]
        assert resp['paginator']['count'] == len(resultSet)
        assert len(resp['items']) == 3
        assert resp['items'][0]['id'] == resultSet[3]['id']
        assert resp['items'][-1]['id'] == resultSet[5]['id']

        # An invalid paginator (here 'page' is less than 1) will result in formencode.Invalid
        # being raised resulting in a response with a 400 status code and a JSON error msg.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'page': 0, 'itemsPerPage': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

        # Some "invalid" paginators will silently fail.  For example, if there is
        # no 'pages' key, then GET /files will just assume there is no paginator
        # and all of the results will be returned.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'pages': 0, 'itemsPerPage': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len([f for f in files if 'N' in f['name']])

        # Adding a 'count' key to the paginator object in the request will spare
        # the server from running query.count().  Note that the server will not
        # attempt to verify the count (since that would defeat the purpose) but
        # will simply pass it back.  The server trusts that the client is passing
        # in a factual count.  Here we pass in an inaccurate count for demonstration.
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'page': 2, 'itemsPerPage': 4, 'count': 750}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['paginator']['count'] == 750
        assert len(resp['items']) == 4
        assert resp['items'][0]['id'] == resultSet[4]['id']
        assert resp['items'][-1]['id'] == resultSet[7]['id']

    #@nottest
    def test_search_z_order_by(self):
        """Tests POST /files/search: order by."""
        files = json.loads(json.dumps(h.getFiles(), cls=h.JSONOLDEncoder))

        # order by name ascending
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'orderBy': ['File', 'name', 'asc']}})
        response = self.app.post(url('/files/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_9.jpg'
        assert resp[0]['name'] == u'name_1.jpg'

        # order by name descending
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'orderBy': ['File', 'name', 'desc']}})
        response = self.app.post(url('/files/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_1.jpg'
        assert resp[0]['name'] == u'name_9.jpg'

        # order by with missing direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'orderBy': ['File', 'name']}})
        response = self.app.post(url('/files/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_9.jpg'
        assert resp[0]['name'] == u'name_1.jpg'

        # order by with unknown direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'orderBy': ['File', 'name', 'descending']}})
        response = self.app.post(url('/files/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_9.jpg'
        assert resp[0]['name'] == u'name_1.jpg'

        # syntactically malformed order by
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'orderBy': ['File']}})
        response = self.app.post(url('/files/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        # searches with lexically malformed order bys
        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'orderBy': ['File', 'foo', 'desc']}})
        response = self.app.post(url('/files/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.foo'] == u'Searching on File.foo is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        jsonQuery = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'orderBy': ['Foo', 'id', 'desc']}})
        response = self.app.post(url('/files/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Foo'] == u'Searching the File model by joining on the Foo model is not possible'
        assert resp['errors']['Foo.id'] == u'Searching on Foo.id is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

    #@nottest
    def test_search_za_restricted(self):
        """Tests SEARCH /files: restricted files."""

        # First restrict the even-numbered forms
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        files = h.getFiles()
        fileCount = len(files)
        for file in files:
            if int(file.name.split('_')[-1].split('.')[0]) % 2 == 0:
                file.tags.append(restrictedTag)
        Session.commit()
        restrictedFiles = Session.query(model.File).filter(
            model.Tag.name==u'restricted').outerjoin(model.File.tags).all()
        restrictedFileCount = len(restrictedFiles)

        # A viewer will only be able to see the unrestricted files
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'regex', '[nN]']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_viewer)
        resp = json.loads(response.body)
        assert len(resp) == restrictedFileCount
        assert 'restricted' not in [
            x['name'] for x in reduce(list.__add__, [f['tags'] for f in resp])]

        # An administrator will be able to access all files
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'regex', '[nN]']}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == fileCount
        assert 'restricted' in [
            x['name'] for x in reduce(list.__add__, [f['tags'] for f in resp])]

        # Filter out restricted files and do pagination
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'regex', '[nN]']},
            'paginator': {'page': 2, 'itemsPerPage': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_viewer)
        resp = json.loads(response.body)
        resultSet = [f for f in files
                        if int(f.name.split('_')[-1].split('.')[0]) % 2 != 0]
        assert resp['paginator']['count'] == restrictedFileCount
        assert len(resp['items']) == 3
        assert resp['items'][0]['id'] == resultSet[3].id

    #@nottest
    def test_search_zb_file_type(self):
        """Tests SEARCH /files: get the different types of files."""
        files = json.loads(json.dumps(h.getFiles(), cls=h.JSONOLDEncoder))

        # Get all files with real files to back them up, (they're the ones with filenames).
        jsonQuery = json.dumps({'query': {'filter': ['File', 'filename', '!=', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['filename']]
        assert len(resp) == 30

        # Get all the subinterval-referencing.
        jsonQuery = json.dumps({'query': {'filter': ['File', 'parentFile', '!=', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['parentFile']]
        assert len(resp) == 10

        # Get all the subinterval-referencing.
        jsonQuery = json.dumps({'query': {'filter': ['File', 'url', '!=', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in files if f['url']]
        assert len(resp) == 10

    #@nottest
    def test_z_cleanup(self):
        """Tests POST /files/search: clean up the database."""

        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        response = self.app.get(url('files'), extra_environ=extra_environ)

        # Remove all of the binary (file system) files created.
        h.clearDirectoryOfFiles(self.filesPath)