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

"""This module tests the collection search functionality, i.e., requests to SEARCH
/collections and POST /collections/search.

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

    config = appconfig('config:test.ini', relative_to='.')
    here = config['here']
    filesPath = h.getOLDDirectoryPath('files', config=config)
    reducedFilesPath = h.getOLDDirectoryPath('reduced_files', config=config)
    testFilesPath = os.path.join(here, 'test_files')

    createParams = {
        'title': u'',
        'type': u'',
        'url': u'',
        'description': u'',
        'markupLanguage': u'',
        'contents': u'',
        'speaker': u'',
        'source': u'',
        'elicitor': u'',
        'enterer': u'',
        'dateElicited': u'',
        'tags': [],
        'files': []
    }

    mdContents = u'\n'.join([
        'Chapter',
        '=======',
        '',
        'Section',
        '-------',
        '',
        '* Item 1',
        '* Item 2',
        '',
        'Section containing forms',
        '------------------------',
        ''
    ])

    rstContents = u'\n'.join([
        'Chapter',
        '=======',
        '',
        'Section',
        '-------',
        '',
        '- Item 1',
        '- Item 2',
        '',
        'Section containing forms',
        '------------------------',
        ''
    ])

    def _createTestModels(self, n=20):
        self._addTestModelsToSession('Tag', n, ['name'])
        self._addTestModelsToSession('Speaker', n, ['firstName', 'lastName', 'dialect'])
        self._addTestModelsToSession('Source', n, ['authorFirstName', 'authorLastName', 'title', 'year'])
        self._addTestModelsToSession('Form', n, ['transcription', 'datetimeEntered', 'datetimeModified'])
        self._addTestModelsToSession('File', n, ['name', 'datetimeEntered', 'datetimeModified'])
        Session.commit()

    def _addTestModelsToSession(self, modelName, n, attrs):
        for i in range(1, n + 1):
            m = getattr(model, modelName)()
            for attr in attrs:
                if attr in ('datetimeModified, datetimeEntered'):
                    setattr(m, attr, datetime.now())
                elif attr == 'year':
                    setattr(m, attr, 2000)
                else:
                    setattr(m, attr, u'%s %s' % (attr, i))
            Session.add(m)

    def _getTestModels(self):
        return {
            'tags': [t.__dict__ for t in h.getTags()],
            'forms': [f.__dict__ for f in h.getForms()],
            'files': [f.__dict__ for f in h.getFiles()],
            'sources': [s.__dict__ for s in h.getSources()],
            'speakers': [s.__dict__ for s in h.getSpeakers()],
            'users': [u.__dict__ for u in h.getUsers()]
        }

    def _createTestData(self, n=20):
        self._createTestModels(n)
        self._createTestCollections(n)

    def _createTestCollections(self, n=20):
        """Create n collections  with various properties.  A testing ground for searches!
        """
        testModels = self._getTestModels()
        tags = dict([(t['name'], t) for t in testModels['tags']])
        viewer = [u for u in testModels['users'] if u['role'] == u'viewer'][0]
        contributor = [u for u in testModels['users'] if u['role'] == u'contributor'][0]
        administrator = [u for u in testModels['users'] if u['role'] == u'administrator'][0]
        for i in range(1, n + 1):

            params = self.createParams.copy()
            params.update({'speaker': testModels['speakers'][i - 1]['id']})

            if i > 10:
                params.update({
                    'title': u'Collection %d' % i,
                    'dateElicited': u'%02d/%02d/%d' % (jan1.month, jan1.day, jan1.year)
                })
            else:
                params.update({
                    'title': u'collection %d' % i,
                    'tags': [tags['name %d' % i]['id']]
                })

            if i in [13, 15]:
                params.update({
                    'dateElicited': u'%02d/%02d/%d' % (jan3.month, jan3.day, jan3.year),
                    'elicitor': contributor['id']
                })

            if i > 5 and i < 16:
                params.update({
                    'files': [testModels['files'][i - 1]['id']],
                    'markupLanguage': u'Markdown',
                    'contents': u'%s\nform[%d]\n' % (self.mdContents, testModels['forms'][i - 1]['id'])
                })
            else:
                params.update({
                    'files': [testModels['files'][0]['id']],
                    'markupLanguage': u'reStructuredText',
                    'contents': u'%s\nform[%d]\n' % (self.rstContents, testModels['forms'][i - 1]['id'])
                })
            params = json.dumps(params)
            response = self.app.post(url('collections'), params, self.json_headers,
                                     self.extra_environ_admin)

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    extra_environ_viewer = {'test.authentication.role': u'viewer'}
    json_headers = {'Content-Type': 'application/json'}
    n = 20

    def tearDown(self):
        pass

    # Initialization for the tests - this needs to be run first in order for the
    # tests to succeed
    #@nottest
    def test_a_initialize(self):
        """Tests POST /collections/search: initialize database."""
        h.clearAllModels(['Language', 'User'])

        # Add a bunch of data to the db.
        self._createTestData(self.n)
        addSEARCHToWebTestValidMethods()

    #@nottest
    def test_search_b_equals(self):
        """Tests POST /collections/search: equals."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', '=', 'Collection 13']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['title'] == u'Collection 13'

    #@nottest
    def test_search_c_not_equals(self):
        """Tests SEARCH /collections: not equals."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Collection', 'title', '=', u'collection 10']]}})
        response = self.app.request(url('collections'), method='SEARCH',
            body=jsonQuery, headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == self.n - 1
        assert u'Collection 10' not in [c['title'] for c in resp]

    #@nottest
    def test_search_d_like(self):
        """Tests POST /collections/search: like."""

        collections = [c.getFullDict() for c in h.getCollections()]

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'like', u'%1%']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'1' in c['title']]
        assert len(resp) == len(resultSet)

        # Case-sensitive like.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'like', u'%C%']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'C' in c['title']]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['or', [
                ['Collection', 'title', 'like', u'C%'],
                ['Collection', 'title', 'like', u'c%']]]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'C' in c['title'] or u'c' in c['title']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_e_not_like(self):
        """Tests SEARCH /collections: not like."""
        collections = [c.getFullDict() for c in h.getCollections()]
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Collection', 'title', 'like', u'%1%']]}})
        response = self.app.request(url('collections'), method='SEARCH',
            body=jsonQuery, headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'1' not in c['title']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_f_regexp(self):
        """Tests POST /collections/search: regular expression."""
        collections = [c.getFullDict() for c in h.getCollections()]

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'regex', u'[345]2']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if re.search('[345]2', c['title'])]
        assert sorted([c['title'] for c in resp]) == sorted([c['title'] for c in resultSet])
        assert len(resp) == len(resultSet)

        # Case-sensitive regexp.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'regex', u'^C']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['title'][0] == u'C']
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'regex', u'^[Cc]']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['title'][0] in [u'C', u'c']]
        assert len(resp) == len(resultSet)

        # Beginning and end of string anchors
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'regex', u'^[Cc]ollection 1$']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['title'] in [u'Collection 1', u'collection 1']]
        assert len(resp) == len(resultSet)

        # Quantifiers
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'regex', u'1{1,}']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if re.search('1{1,}', c['title'])]
        assert len(resp) == len(resultSet)

        # Quantifiers
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'regex', u'[123]{2,}']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if re.search('[123]{2,}', c['title'])]
        assert len(resp) == len(resultSet)

        # Bad regex
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'regex', u'[123]{3,2}']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    #@nottest
    def test_search_g_not_regexp(self):
        """Tests SEARCH /collections: not regular expression."""
        collections = [c.getFullDict() for c in h.getCollections()]
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Collection', 'title', 'regexp', u'[345]2']]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if not re.search('[345]2', c['title'])]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_h_empty(self):
        """Tests POST /collections/search: is NULL."""
        collections = [c.getFullDict() for c in h.getCollections()]

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'description', '=', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['description'] is None]
        assert len(resp) == len(resultSet)

        # Same as above but with a double negative
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Collection', 'description', '!=', None]]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_i_not_empty(self):
        """Tests SEARCH /collections: is not NULL."""
        collections = [c.getFullDict() for c in h.getCollections()]
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Collection', 'description', '=', None]]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['description'] is not None]
        assert len(resp) == len(resultSet)

        # Same as above, but with !=, i.e., __ne__
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'description', '!=', None]}})
        response = self.app.request(url('collections'), body=jsonQuery, method='SEARCH',
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_j_invalid_json(self):
        """Tests POST /collections/search: invalid JSON params."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Collection', 'description', '=', None]]}})
        jsonQuery = jsonQuery[:-1]  # Cut off the end to make it bad!
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'JSON decode error: the parameters provided were not valid JSON.'

    #@nottest
    def test_search_k_malformed_query(self):
        """Tests SEARCH /collections: malformed query."""

        collections = [c.getFullDict() for c in h.getCollections()]

        # TypeError - bad num args: 'NOT' will be treated as the first arg to
        # _getSimpleFilterExpression and ['Collection', 'title', '=', 10] will be passed
        # as the second -- two more are required.
        jsonQuery = json.dumps({'query': {'filter': ['NOT', ['Collection', 'id', '=', 10]]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # After recognizing 'not', the query builder will look at only the next
        # list and ignore all the rest.
        jsonQuery = json.dumps(
            {'query': {'filter':
                ['not',
                    ['Collection', 'title', '=', 'Collection 10'], 
                    ['Collection', 'title', '=', 'Collection 10'],
                    ['Collection', 'title', '=', 'Collection 10']]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['title'] != u'Collection 10']
        assert len(resp) == len(resultSet)
        assert 'Collection 10' not in [c['title'] for c in resp]

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps({'query': {'filter': ['not']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[0] is called.
        jsonQuery = json.dumps({'query': {'filter': []}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps({'query': {'filter': ['and']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['IndexError'] == u'list index out of range'

        # TypeError bad num args will be triggered when _getSimpleFilterExpression is
        # called on a string whose len is not 4, i.e., 'id' or '='.
        jsonQuery = json.dumps({'query': {'filter': ['and', ['Collection', 'id', '=', '1099']]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'TypeError' in resp['errors']
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # TypeError when asking whether [] is in a dict (lists are unhashable)
        jsonQuery = json.dumps({'query': {'filter': [[], 'a', 'a', 'a']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['TypeError'] == u"unhashable type: 'list'"
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # With no 'query' attribute, the SQLAQueryBuilder will be passed None and
        # will immediately raise an AttributeError.
        jsonQuery = json.dumps({'filter': ['Collection', 'id', '=', 2]})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

        # With no 'filter' attribute, the SQLAQueryBuilder will be passed a list
        # will immediately raise an AttributeError when it tries to call [...].get('filter').
        jsonQuery = json.dumps({'query': ['Collection', 'id', '=', 2]})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    #@nottest
    def test_search_l_lexical_semantic_error(self):
        """Tests POST /collections/search: lexical & semantic errors.

        These are when SQLAQueryBuilder.py raises a OLDSearchParseError because a
        relation is not permitted, e.g., 'contains', or not permitted for a
        given attribute.
        """

        # searchParser.py does not allow the contains relation (OLDSearchParseError)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'title', 'contains', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'Collection.title.contains' in resp['errors']

        # model.Collection.tags.__eq__('abcdefg') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'tags', '=', u'abcdefg']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

        # model.Collection.tags.regexp('xyz') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'tags', 'regex', u'xyz']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['Collection.tags.regex'] == u'The relation regex is not permitted for Collection.tags'

        # model.Collection.tags.like('title') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'tags', 'like', u'abc']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Collection.tags.like'] == \
            u'The relation like is not permitted for Collection.tags'

        # model.Collection.tags.__eq__('tag') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'tags', '__eq__', u'tag']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'InvalidRequestError' in resp['errors']

    #@nottest
    def test_search_m_conjunction(self):
        """Tests SEARCH /collections: conjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]
        models = self._getTestModels()
        collections = [c.getFullDict() for c in h.getCollections()]

        # 1 conjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'and', [
                ['Collection', 'title', 'like', u'%2%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'2' in c['title']]
        assert len(resp) == len(resultSet)

        # 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['Collection', 'title', 'like', u'%2%'],
                ['Collection', 'title', 'like', u'%1%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'2' in c['title'] and u'1' in c['title']]
        assert len(resp) == len(resultSet)
        assert sorted([c['title'] for c in resp]) == sorted([c['title'] for c in resultSet])

        # More than 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['Collection', 'title', 'like', u'%1%'],
                ['Collection', 'elicitor', '=', None],
                ['Collection', 'speaker', '!=', None]
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'1' in c['title'] and
                     c['elicitor'] is None and c['speaker'] is not None]
        assert resp
        assert len(resp) == len(resultSet)
        assert sorted([c['title'] for c in resp]) == sorted([c['title'] for c in resultSet])

        # Multiple redundant conjuncts -- proof of possibility
        query = {'query': {'filter': [
            'and', [
                ['Collection', 'title', 'like', u'%1%'],
                ['Collection', 'title', 'like', u'%1%'],
                ['Collection', 'title', 'like', u'%1%'],
                ['Collection', 'title', 'like', u'%1%'],
                ['Collection', 'title', 'like', u'%1%'],
                ['Collection', 'title', 'like', u'%1%'],
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'1' in c['title']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_n_disjunction(self):
        """Tests POST /collections/search: disjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]
        collections = [c.getFullDict() for c in h.getCollections()]

        # 1 disjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'or', [
                ['Collection', 'title', 'like', u'%2%']   # 19 total
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'2' in c['title']]
        assert len(resp) == len(resultSet)

        # 2 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['Collection', 'title', 'like', u'%2%'],
                ['Collection', 'title', 'like', u'%1%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'2' in c['title'] or u'1' in c['title']]
        assert len(resp) == len(resultSet)

        # 3 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['Collection', 'title', 'like', u'%2%'],
                ['Collection', 'title', 'like', u'%1%'],
                ['Collection', 'elicitor', 'id', '=', contributor.id]
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'2' in c['title'] or u'1' in c['title']
                     or (c['elicitor'] and c['elicitor']['id'] == contributor.id)]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_o_int(self):
        """Tests SEARCH /collections: integer searches."""

        collections = [c.getFullDict() for c in h.getCollections()]
        collectionIds = [c['id'] for c in collections]

        # = int
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'id', '=', collectionIds[1]]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['id'] == collectionIds[1]

        # < int (str)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'id', '<', str(collectionIds[16])]}}) # Thanks to SQLAlchemy, a string will work here too
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['id'] < collectionIds[16]]
        assert len(resp) == len(resultSet)

        # >= int
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'id', '>=', collectionIds[9]]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['id'] >= collectionIds[9]]
        assert len(resp) == len(resultSet)

        # in array
        jsonQuery = json.dumps(
            {'query': {'filter':
                ['Collection', 'id', 'in', [collectionIds[1], collectionIds[3], collectionIds[8], collectionIds[19]]]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4
        assert sorted([c['id'] for c in resp]) == [collectionIds[1], collectionIds[3], collectionIds[8], collectionIds[19]]

        # in None -- Error
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'id', 'in', None]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Collection.id.in_'] == u"Invalid filter expression: Collection.id.in_(None)"

        # in int -- Error
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'id', 'in', 2]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Collection.id.in_'] == u"Invalid filter expression: Collection.id.in_(2)"

        # regex int - The OLD's Python-based regexp implementation for SQLite will
        # automatically convert a non-string field value to a string before doing
        # the regexp comparison.  I believe that this parallels MySQL's regexp
        # behaviour accurately.
        strPatt = u'[12][12]'
        patt = re.compile(strPatt)
        expectedIdMatches = [c['id'] for c in collections if patt.search(str(c['id']))]
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'id', 'regex', strPatt]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedIdMatches)
        assert sorted([c['id'] for c in resp]) == sorted(expectedIdMatches)

        # like int - RDBMS treats ints as strings for LIKE search
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'id', 'like', u'%2%']}})
        expectedMatches = [i for i in collectionIds if u'2' in str(i)]
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedMatches)

    #@nottest
    def test_search_p_date(self):
        """Tests POST /collections/search: date searches."""
        collections = [c.getFullDict() for c in h.getCollections()]

        # = date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '=', jan1.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if isofy(c['dateElicited']) == jan1.isoformat()]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '=', jan3.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if isofy(c['dateElicited']) == jan3.isoformat()]
        assert len(resp) == len(resultSet)

        # != date -- *NOTE:* the NULL dateElicited values will not be counted.
        # The implicit query is 'is not null and != 2012-01-01'
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '!=', jan1.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if isofy(c['dateElicited']) is not None and
                     isofy(c['dateElicited']) != jan1.isoformat()]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '!=', jan3.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if isofy(c['dateElicited']) is not None and
                     isofy(c['dateElicited']) != jan3.isoformat()]
        assert len(resp) == len(resultSet)

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter': [
            'or', [['Collection', 'dateElicited', '!=', jan1.isoformat()],
                ['Collection', 'dateElicited', '=', None]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if isofy(c['dateElicited']) != jan1.isoformat()]
        assert len(resp) == len(resultSet)

        # < date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '<', jan1.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and c['dateElicited'] < jan1]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '<', jan3.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and c['dateElicited'] < jan3]
        assert len(resp) == len(resultSet)

        # <= date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '<=', jan3.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and c['dateElicited'] <= jan3]
        assert len(resp) == len(resultSet)

        # > date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '>', jan1.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and c['dateElicited'] > jan2]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '>', '0001-01-01']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and
                     isofy(c['dateElicited']) > '0001-01-01']
        assert len(resp) == len(resultSet)

        # >= date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '>=', jan1.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and c['dateElicited'] >= jan1]
        assert len(resp) == len(resultSet)

        # =/!= None
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'dateElicited', '=', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is None]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '__ne__', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_q_date_invalid(self):
        """Tests SEARCH /collections: invalid date searches."""

        collections = [c.getFullDict() for c in h.getCollections()]

        # = invalid date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '=', '12-01-01']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 12-01-01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', '=', '2012-01-32']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 2012-01-32'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on invalid date will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', 'regex', '01']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on valid date will work and will act just like = -- no point
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', 'regex', '2012-01-01']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and
                     c['dateElicited'].isoformat() == '2012-01-01']
        assert len(resp) == len(resultSet)

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', 'like', '2012-01-01']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(resultSet)

        # in_ on a date.  This will raise a TypeError ('datetime.date' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', 'in', '2012-01-02']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Collection.dateElicited.in_'] == u'Invalid filter expression: Collection.dateElicited.in_(datetime.date(2012, 1, 2))'

        # in_ on a list of dates works (SQLAQueryBuilder generates a list of date objects)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'dateElicited', 'in', ['2012-01-01', '2012-01-03']]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['dateElicited'] is not None and
                     c['dateElicited'].isoformat() in ['2012-01-01', '2012-01-03']]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_r_datetime(self):
        """Tests POST /collections/search: datetime searches."""
        collections = [c.getFullDict() for c in h.getCollections()]

        # = datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] == todayTimestamp]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] == yesterdayTimestamp]
        assert len(resp) == len(resultSet)

        # != datetime -- *NOTE:* the NULL datetimeEntered values will not be counted.
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '!=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] != todayTimestamp]
        assert len(resp) == len(resultSet)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '!=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] != yesterdayTimestamp]
        assert len(resp) == len(resultSet)

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter':
            ['or', [['Collection', 'datetimeEntered', '!=', todayTimestamp.isoformat()],
                ['Collection', 'datetimeEntered', '=', None]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is None or
                     c['datetimeEntered'] != todayTimestamp]
        assert len(resp) == len(resultSet)

        # < datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '<', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'] < todayTimestamp]
        assert len(resp) == len(resultSet)

        # <= datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '<=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'] <= todayTimestamp]
        assert len(resp) == len(resultSet)

        # > datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '>', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'] > todayTimestamp]
        assert len(resp) == len(resultSet)
        # Note: Python2.6/Debian(?) bug: using a year before 1900 will cause problems: 
        # ValueError: year=1 is before 1900; the datetime strftime() methods require year >= 1900
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '>', '1901-01-01T09:08:07']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'].isoformat() > '1901-01-01T09:08:07']
        assert len(resp) == len(resultSet)

        # >= datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '>=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'] >= yesterdayTimestamp]
        assert len(resp) == len(resultSet)

        # =/!= None
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '=', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is None]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeEntered', '__ne__', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None]
        assert len(resp) == len(resultSet)

        # datetime in today
        midnightToday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        midnightTomorrow = midnightToday + dayDelta
        query = {'query': {'filter':
            ['and', [['Collection', 'datetimeEntered', '>', midnightToday.isoformat()],
                         ['Collection', 'datetimeEntered', '<', midnightTomorrow.isoformat()]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'] > midnightToday and
                     c['datetimeEntered'] < midnightTomorrow]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_s_datetime_invalid(self):
        """Tests SEARCH /collections: invalid datetime searches."""
        collections = [c.getFullDict() for c in h.getCollections()]

        # = invalid datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeModified', '=', '12-01-01T09']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 12-01-01T09'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeModified', '=', '2012-01-30T09:08:61']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 2012-01-30T09:08:61'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # Trailing period and too many microseconds will both succeed.
        jsonQuery = json.dumps({'query': {'filter':
                ['Collection', 'datetimeModified', '=', '2012-01-30T09:08:59.123456789123456789123456789']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'datetimeModified', '=', '2012-01-30T09:08:59.']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)

        # regex on invalid datetime will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'datetimeModified', 'regex', '01']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 01'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # regex on valid datetime will work and will act just like = -- no point
        jsonQuery = json.dumps({'query': {'filter':
                ['Collection', 'datetimeEntered', 'regex', todayTimestamp.isoformat()]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'] == todayTimestamp]
        assert len(resp) == len(resultSet)

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps({'query': {'filter':
                ['Collection', 'datetimeModified', 'like', todayTimestamp.isoformat()]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeEntered'] is not None and
                     c['datetimeEntered'] == todayTimestamp]
        assert len(resp) == len(resultSet)

        # in_ on a datetime.  This will raise a TypeError ('datetime.datetime' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'datetimeModified', 'in', todayTimestamp.isoformat()]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Collection.datetimeModified.in_'] == \
            u'Invalid filter expression: Collection.datetimeModified.in_(%s)' % repr(todayTimestamp)

        # in_ on a list of datetimes works (SQLAQueryBuilder generates a list of datetime objects)
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'datetimeModified', 'in',
                [todayTimestamp.isoformat(), yesterdayTimestamp.isoformat()]]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['datetimeModified'] is not None and
                     c['datetimeModified'] in (todayTimestamp, yesterdayTimestamp)]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_t_many_to_one(self):
        """Tests POST /collections/search: searches on many-to-one attributes."""
        collections = [c.getFullDict() for c in h.getCollections()]

        testModels = self._getTestModels()
        users = h.getUsers()
        forms = h.getForms()
        viewer = [u for u in users if u.role == u'viewer'][0]
        contributor = [u for u in users if u.role == u'contributor'][0]
        administrator = [u for u in users if u.role == u'administrator'][0]

        # = int
        jsonQuery = json.dumps(
            {'query': {'filter': ['Collection', 'enterer', 'id', '=', contributor.id]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['enterer']['id'] == contributor.id]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'speaker', 'id', '=', testModels['speakers'][0]['id']]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['speaker'] and
                     c['speaker']['id'] == testModels['speakers'][0]['id']]
        assert len(resp) == len(resultSet)

        # in array of ints
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'speaker', 'id', 'in', [s['id'] for s in testModels['speakers']]]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['speaker'] and
                     c['speaker']['id'] in [s['id'] for s in testModels['speakers']]]
        assert len(resp) == len(resultSet)

        # <
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'speaker', 'id', '<', 15]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['speaker'] and
                     c['speaker']['id'] < 15]
        assert len(resp) == len(resultSet)

        # regex
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'speaker', 'id', 'regex', '5']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['speaker'] and
                     u'5' in str(c['speaker']['id'])]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'speaker', 'id', 'regex', '[56]']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['speaker'] and
                     re.search('[56]', str(c['speaker']['id']))]
        assert len(resp) == len(resultSet)

        # like
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'speaker', 'id', 'like', '%5%']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['speaker'] and
                     '5' in str(c['speaker']['id'])]
        assert len(resp) == len(resultSet)

    #@nottest
    def test_search_v_many_to_many(self):
        """Tests POST /collections/search: searches on many-to-many attributes, i.e., Tag, Form, File."""
        collections = [c.getFullDict() for c in h.getCollections()]

        # tag.name =
        jsonQuery = json.dumps({'query': {'filter': ['Tag', 'name', '=', 'name 6']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if 'name 6' in [t['name'] for t in c['tags']]]
        #log.debug(len(resp))
        #log.debug([c['tags'] for c in collections])
        assert resp
        assert len(resp) == len(resultSet)

        # form.transcription like
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'like', '%transcription 6%']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections
                     if 'transcription 6' in ''.join([fo['transcription'] for fo in c['forms']])]
        assert resp
        assert len(resp) == len(resultSet)

        # file.name like
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'like', '%name 9%']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections
                     if 'name 6' in ''.join([fi['name'] for fi in c['files']])]
        assert resp
        assert len(resp) == len(resultSet)

        # form.transcription regexp
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'regex', 'transcription [12]']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections
                     if re.search('transcription [12]', ''.join([fo['transcription'] for fo in c['forms']]))]
        assert resp
        assert len(resp) == len(resultSet)

        # tag.name in_
        names = [u'name 17', u'name 19', u'name 9']
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', 'in_', names]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if set(names) & set([t['name'] for t in c['tags']])]
        #log.debug([c['tags'] for c in collections])
        assert resp
        assert len(resp) == len(resultSet)

        # tag.name <
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', '<', u'name 2']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if [t for t in c['tags'] if t['name'] < u'name 2']]
        assert resp
        assert len(resp) == len(resultSet)

        # form.datetimeEntered
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'datetimeEntered', '>', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections
                     if [fo for fo in c['forms'] if fo['datetimeEntered'] > yesterdayTimestamp]]
        assert resp
        assert len(resp) == len(resultSet)

        files = Session.query(model.File).all()
        files = dict([(f.id, f) for f in files])
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'datetimeModified', '>', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if [
            fi for fi in c['files'] if files[fi['id']].datetimeEntered > yesterdayTimestamp]]
        assert resp
        assert len(resp) == len(resultSet)

        # To search for the presence/absence of tags/forms, one must use the
        # tags/forms attributes of the File model.
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'tags', '=', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if not c['tags']]
        assert len(resp) == len(resultSet)

        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'forms', '!=', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['forms']]
        assert resp
        assert len(resp) == len(resultSet)

        # Using anything other than =/!= on Form.tags/collections/collections will raise an error.
        jsonQuery = json.dumps({'query': {'filter': ['Collection', 'tags', 'like', None]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp
        assert resp['errors']['Collection.tags.like'] == u'The relation like is not permitted for Collection.tags'

        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'forms', '=', 'form 2']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

    #@nottest
    def test_search_w_in(self):
        """Tests SEARCH /collections: searches using the in_ relation."""
        collections = [c.getFullDict() for c in h.getCollections()]

        # Array value -- all good.
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'title', 'in', ['collection 1', 'Collection 11']]}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if c['title'] in ['collection 1', 'Collection 11']]
        assert resp
        assert len(resp) == len(resultSet)

        # String value -- no error because strings are iterable; but no results
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'title', 'in', 'Collection 1']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0

    #@nottest
    def test_search_x_complex(self):
        """Tests POST /collections/search: complex searches."""
        collections = [c.getFullDict() for c in h.getCollections()]

        # A fairly complex search
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['Tag', 'name', 'like', '%1%'],
                ['not', ['Collection', 'title', 'regex', '[12][5-7]']],
                ['or', [
                    ['Collection', 'datetimeEntered', '>', todayTimestamp.isoformat()],
                    ['Collection', 'dateElicited', '=', jan1.isoformat()]]]]]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if
            '1' in ' '.join([t['name'] for t in c['tags']]) and
            not re.search('[12][5-7]', c['title']) and
            (todayTimestamp < c['datetimeEntered'] or
            (c['dateElicited'] and jan1 < c['dateElicited']))]
        assert resp
        assert len(resp) == len(resultSet)

        # A complex search entailing multiple joins
        tagNames = ['name 2', 'name 4', 'name 8']
        patt = '([13579][02468])|([02468][13579])'
        jsonQuery = json.dumps({'query': {'filter': [
            'or', [
                ['Form', 'transcription', 'like', '%1%'],
                ['Tag', 'name', 'in', tagNames],
                ['and', [
                    ['not', ['Collection', 'title', 'regex', patt]],
                    ['Collection', 'dateElicited', '!=', None]]]]]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if
            '1' in ' '.join([fo['transcription'] for fo in c['forms']]) or
            set([t['name'] for t in c['tags']]) & set(tagNames) or
            (not re.search(patt, c['title']) and
             c['dateElicited'] is not None)]
        assert resp
        assert len(resp) == len(resultSet)

        # A complex search ...  The implicit assertion is that a 200 status
        # code is returned.  At this point I am not going to bother attempting to
        # emulate this query in Python ...
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['Collection', 'title', 'like', '%5%'],
                ['Collection', 'description', 'regex', '.'],
                ['not', ['Tag', 'name', 'like', '%6%']],
                ['or', [
                    ['Collection', 'datetimeEntered', '<', todayTimestamp.isoformat()],
                    ['not', ['Collection', 'dateElicited', 'in', [jan1.isoformat(), jan3.isoformat()]]],
                    ['and', [
                        ['Collection', 'enterer', 'id', 'regex', '[135680]'],
                        ['Collection', 'id', '<', 90]
                    ]]
                ]],
                ['not', ['not', ['not', ['Tag', 'name', '=', 'name 7']]]]
            ]
        ]}})
        response = self.app.post(url('/collections/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

    #@nottest
    def test_search_y_paginator(self):
        """Tests SEARCH /collections: paginator."""
        collections = json.loads(json.dumps(h.getCollections(), cls=h.JSONOLDEncoder))

        # A basic search with a paginator provided.
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'like', '%C%']},
            'paginator': {'page': 2, 'itemsPerPage': 3}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [c for c in collections if u'C' in c['title']]
        assert resp['paginator']['count'] == len(resultSet)
        assert len(resp['items']) == 3
        assert resp['items'][0]['id'] == resultSet[3]['id']
        assert resp['items'][-1]['id'] == resultSet[5]['id']

        # An invalid paginator (here 'page' is less than 1) will result in formencode.Invalid
        # being raised resulting in a response with a 400 status code and a JSON error msg.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['Collection', 'title', 'like', '%C%']},
            'paginator': {'page': 0, 'itemsPerPage': 3}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

        # Some "invalid" paginators will silently fail.  For example, if there is
        # no 'pages' key, then GET /files will just assume there is no paginator
        # and all of the results will be returned.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['Collection', 'title', 'like', '%C%']},
            'paginator': {'pages': 0, 'itemsPerPage': 3}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len([c for c in collections if u'C' in c['title']])

        # Adding a 'count' key to the paginator object in the request will spare
        # the server from running query.count().  Note that the server will not
        # attempt to verify the count (since that would defeat the purpose) but
        # will simply pass it back.  The server trusts that the client is passing
        # in a factual count.  Here we pass in an inaccurate count for demonstration.
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'like', '%C%']},
            'paginator': {'page': 2, 'itemsPerPage': 4, 'count': 750}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['paginator']['count'] == 750
        assert len(resp['items']) == 4
        assert resp['items'][0]['id'] == resultSet[4]['id']
        assert resp['items'][-1]['id'] == resultSet[7]['id']

    #@nottest
    def test_search_z_order_by(self):
        """Tests POST /collections/search: order by."""
        collections = json.loads(json.dumps(h.getCollections(), cls=h.JSONOLDEncoder))

        # order by name ascending
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'regex', '[cC]'],
                'orderBy': ['Collection', 'title', 'asc']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(collections)
        assert resp[-1]['title'] == u'collection 9'
        assert resp[0]['title'] == u'collection 1'

        # order by name descending
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'regex', '[nN]'],
                'orderBy': ['Collection', 'title', 'desc']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(collections)
        assert resp[-1]['title'] == u'collection 1'
        assert resp[0]['title'] == u'collection 9'

        # order by with missing direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'regex', '[nN]'],
                'orderBy': ['Collection', 'title']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(collections)
        assert resp[-1]['title'] == u'collection 9'
        assert resp[0]['title'] == u'collection 1'

        # order by with unknown direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'regex', '[nN]'],
                'orderBy': ['Collection', 'title', 'descending']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(collections)
        assert resp[-1]['title'] == u'collection 9'
        assert resp[0]['title'] == u'collection 1'

        # syntactically malformed order by
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'regex', '[nN]'],
                'orderBy': ['Collection']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        # searches with lexically malformed order bys
        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'regex', '[nN]'],
                'orderBy': ['Collection', 'foo', 'desc']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Collection.foo'] == u'Searching on Collection.foo is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        jsonQuery = json.dumps({'query': {
                'filter': ['Collection', 'title', 'regex', '[nN]'],
                'orderBy': ['Foo', 'id', 'desc']}})
        response = self.app.post(url('/collections/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Foo'] == u'Searching the Collection model by joining on the Foo model is not possible'
        assert resp['errors']['Foo.id'] == u'Searching on Foo.id is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

    #@nottest
    def test_search_za_restricted(self):
        """Tests SEARCH /collections: restricted collections."""

        # First restrict the even-numbered collections
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        collections = h.getCollections()
        collectionCount = len(collections)
        for collection in collections:
            if int(collection.title.split(' ')[-1]) % 2 == 0:
                collection.tags.append(restrictedTag)
        Session.commit()
        restrictedCollections = Session.query(model.Collection).filter(
            model.Tag.name==u'restricted').outerjoin(model.Collection.tags).all()
        restrictedCollectionCount = len(restrictedCollections)

        # A viewer will only be able to see the unrestricted collection
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'title', 'regex', '[cC]']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_viewer)
        resp = json.loads(response.body)
        assert len(resp) == restrictedCollectionCount
        assert 'restricted' not in [
            x['name'] for x in reduce(list.__add__, [c['tags'] for c in resp])]

        # An administrator will be able to access all collections
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'title', 'regex', '[cC]']}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == collectionCount
        assert 'restricted' in [
            x['name'] for x in reduce(list.__add__, [c['tags'] for c in resp])]

        # Filter out restricted collection and do pagination
        jsonQuery = json.dumps({'query': {'filter':
            ['Collection', 'title', 'regex', '[cC]']},
            'paginator': {'page': 2, 'itemsPerPage': 3}})
        response = self.app.request(url('collections'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_viewer)
        resp = json.loads(response.body)
        resultSet = [c for c in collections
                     if int(c.title.split(' ')[-1]) % 2 != 0]
        assert resp['paginator']['count'] == restrictedCollectionCount
        assert len(resp['items']) == 3
        assert resp['items'][0]['id'] == resultSet[3].id

    #@nottest
    def test_z_cleanup(self):
        """Tests POST /collections/search: clean up the database."""

        h.clearAllModels()
        administrator = h.generateDefaultAdministrator(config=self.config)
        contributor = h.generateDefaultContributor(config=self.config)
        viewer = h.generateDefaultViewer(config=self.config)
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        response = self.app.get(url('collections'), extra_environ=extra_environ)

        # Remove all of the binary (file system) files created.
        h.clearDirectoryOfFiles(self.filesPath)