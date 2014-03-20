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
WSGIWarning when unknown HTTP methods (e.g., SEARCH) are used.  To prevent
this, I altered the global valid_methods tuple of webtest.lint at runtime by
adding a 'SEARCH' method (see _add_SEARCH_to_web_test_valid_methods() below).
"""

import re
import os
from base64 import encodestring
from onlinelinguisticdatabase.tests import TestController, url
from nose.tools import nottest
import simplejson as json
import logging
from datetime import date, datetime, timedelta
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h

log = logging.getLogger(__name__)

# Global temporal objects -- useful for creating the data upon which to search
# and for formulating assertions about the results of those searches.
today_timestamp = datetime.now()
day_delta = timedelta(1)
yesterday_timestamp = today_timestamp - day_delta
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

class TestFormsSearchController(TestController):

    def _create_test_models(self, n=20):
        self._add_test_models_to_session('Tag', n, ['name'])
        self._add_test_models_to_session('Speaker', n, ['first_name', 'last_name', 'dialect'])
        self._add_test_models_to_session('Form', n, ['transcription', 'datetime_entered', 'datetime_modified'])
        Session.commit()

    def _add_test_models_to_session(self, model_name, n, attrs):
        for i in range(1, n + 1):
            m = getattr(model, model_name)()
            for attr in attrs:
                if attr in ('datetime_modified, datetime_entered'):
                    setattr(m, attr, datetime.now())
                else:
                    setattr(m, attr, u'%s %s' % (attr, i))
            Session.add(m)

    def _get_test_models(self):
        default_models = {
            'tags': [t.__dict__ for t in h.get_tags()],
            'forms': [f.__dict__ for f in h.get_forms()],
            'speakers': [s.__dict__ for s in h.get_speakers()],
            'users': [u.__dict__ for u in h.get_users()]
        }
        return default_models

    def _create_test_data(self, n=20):
        self._create_test_models(n)
        self._create_test_files(n)

    def _create_test_files(self, n=20):
        """Create n files with various properties.  A testing ground for searches!
        """
        test_models = self._get_test_models()
        ids = []
        for i in range(1, n + 1):
            jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
            jpg_base64 = encodestring(open(jpg_file_path).read())
            wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
            wav_base64 = encodestring(open(wav_file_path).read())
            params = self.file_create_params.copy()

            if i < 11:
                params.update({
                    'base64_encoded_file': jpg_base64,
                    'filename': u'name_%d.jpg' % i,
                    'name': u'name_%d.jpg' % i,
                    'tags': [test_models['tags'][i - 1]['id']]
                })
            elif i < 21:
                params.update({
                    'base64_encoded_file': jpg_base64,
                    'filename': u'Name_%d.jpg' % i,
                    'date_elicited': u'%02d/%02d/%d' % (jan1.month, jan1.day, jan1.year)
                })
            elif i < 31:
                params.update({
                    'base64_encoded_file': wav_base64,
                    'filename': u'Name_%d.wav' % i,
                    'date_elicited': u'%02d/%02d/%d' % (jan1.month, jan1.day, jan1.year)
                })
            elif i < 41:
                params.update({'parent_file': ids[-10], 'start': 1, 'end': 2,
                               'name': u'Name_%d' % i})
            else:
                params.update({'name': u'Name_%d' % i, 'MIME_type': u'video/mpeg',
                               'url': 'http://vimeo.com/54144270'})

            if i in [36, 37]:
                del params['name']

            if i in [13, 15]:
                params.update({
                    'date_elicited': u'%02d/%02d/%d' % (jan3.month, jan3.day, jan3.year)
                })

            if i > 5 and i < 16:
                params.update({
                    'forms': [test_models['forms'][i - 1]['id']]
                })

            params = json.dumps(params)
            response = self.app.post(url('files'), params, self.json_headers,
                                     self.extra_environ_admin)
            resp = json.loads(response.body)
            ids.append(resp['id'])
    n = 50

    def tearDown(self):
        """Vacuous teardown prevents TestController's tearDown from destroying 
        data between test methods."""
        pass

    # Initialization for the tests - this needs to be run first in order for the
    # tests to succeed
    @nottest
    def test_a_initialize(self):
        """Tests POST /files/search: initialize database."""
        # Add a bunch of data to the db.
        self._create_test_data(self.n)
        self._add_SEARCH_to_web_test_valid_methods()

    @nottest
    def test_search_b_equals(self):
        """Tests POST /files/search: equals."""
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', '=', 'name_10.jpg']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['name'] == u'name_10.jpg'

    @nottest
    def test_search_c_not_equals(self):
        """Tests SEARCH /files: not equals."""
        json_query = json.dumps(
            {'query': 
                {'filter': ['not', ['File', 'name', '=', u'name_10.jpg']]}})
        response = self.app.request(
            url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == self.n - 1
        assert u'name_10.jpg' not in [f['name'] for f in resp]

    @nottest
    def test_search_d_like(self):
        """Tests POST /files/search: like."""

        files = [f.get_dict() for f in h.get_files()]

        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'like', u'%1%']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'1' in f['name']]
        assert len(resp) == len(result_set)

        # Case-sensitive like.  This shows that _collate_attribute is working
        # as expected in SQLAQueryBuilder.
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'like', u'%N%']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'N' in f['name']]
        assert len(resp) == len(result_set)

        json_query = json.dumps(
            {'query': {'filter': ['or', [
                ['File', 'name', 'like', u'N%'],
                ['File', 'name', 'like', u'n%']]]}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'N' in f['name'] or u'n' in f['name']]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_e_not_like(self):
        """Tests SEARCH /files: not like."""
        files = [f.get_dict() for f in h.get_files()]
        json_query = json.dumps(
            {'query': {'filter': ['not', ['File', 'name', 'like', u'%1%']]}})
        response = self.app.request(url('files'), method='SEARCH',
            body=json_query, headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'1' not in f['name']]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_f_regexp(self):
        """Tests POST /files/search: regular expression."""
        files = [f.get_dict() for f in h.get_files()]

        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'[345]2']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if re.search('[345]2', f['name'])]
        assert sorted([f['name'] for f in resp]) == sorted([f['name'] for f in result_set])
        assert len(resp) == len(result_set)

        # Case-sensitive regexp.  This shows that _collate_attribute is working
        # as expected in SQLAQueryBuilder.
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'^N']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['name'][0] == u'N']
        assert len(resp) == len(result_set)

        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'^[Nn]']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['name'][0] in [u'N', 'n']]
        assert len(resp) == len(result_set)

        # Beginning and end of string anchors
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'^[Nn]ame_1.jpg$']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['name'] in [u'Name_1.jpg', u'name_1.jpg']]
        assert len(resp) == len(result_set)

        # Quantifiers
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'1{1,}']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if re.search('1{1,}', f['name'])]
        assert len(resp) == len(result_set)

        # Quantifiers
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'[123]{2,}']}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if re.search('[123]{2,}', f['name'])]
        assert len(resp) == len(result_set)

        # Bad regex
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'regex', u'[123]{3,2}']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    @nottest
    def test_search_g_not_regexp(self):
        """Tests SEARCH /files: not regular expression."""
        files = [f.get_dict() for f in h.get_files()]
        json_query = json.dumps(
            {'query': {'filter': ['not', ['File', 'name', 'regexp', u'[345]2']]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if not re.search('[345]2', f['name'])]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_h_empty(self):
        """Tests POST /files/search: is NULL."""
        files = [f.get_dict() for f in h.get_files()]

        json_query = json.dumps(
            {'query': {'filter': ['File', 'description', '=', None]}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['description'] is None]
        assert len(resp) == len(result_set)

        # Same as above but with a double negative
        json_query = json.dumps(
            {'query': {'filter': ['not', ['File', 'description', '!=', None]]}})
        response = self.app.post(url('/files/search'), json_query,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(result_set)

    @nottest
    def test_search_i_not_empty(self):
        """Tests SEARCH /files: is not NULL."""
        files = [f.get_dict() for f in h.get_files()]
        json_query = json.dumps(
            {'query': {'filter': ['not', ['File', 'description', '=', None]]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['description'] is not None]
        assert len(resp) == len(result_set)

        # Same as above, but with !=, i.e., __ne__
        json_query = json.dumps(
            {'query': {'filter': ['File', 'description', '!=', None]}})
        response = self.app.request(url('files'), body=json_query, method='SEARCH',
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(result_set)

    @nottest
    def test_search_j_invalid_json(self):
        """Tests POST /files/search: invalid JSON params."""
        json_query = json.dumps(
            {'query': {'filter': ['not', ['File', 'description', '=', None]]}})
        json_query = json_query[:-1]  # Cut off the end to make it bad!
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'JSON decode error: the parameters provided were not valid JSON.'

    @nottest
    def test_search_k_malformed_query(self):
        """Tests SEARCH /files: malformed query."""

        files = [f.get_dict() for f in h.get_files()]

        # TypeError - bad num args: 'NOT' will be treated as the first arg to
        # _get_simple_filter_expression and ['File', 'name', '=', 10] will be passed
        # as the second -- two more are required.
        json_query = json.dumps({'query': {'filter': ['NOT', ['File', 'id', '=', 10]]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # After recognizing 'not', the query builder will look at only the next
        # list and ignore all the rest.
        json_query = json.dumps(
            {'query': {'filter':
                ['not',
                    ['File', 'name', '=', 'name_10.jpg'], 
                    ['File', 'name', '=', 'name_10.jpg'],
                    ['File', 'name', '=', 'name_10.jpg']]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['name'] != u'name_10.jpg']
        assert len(resp) == len(result_set)
        assert 'name 10' not in [f['name'] for f in resp]

        # IndexError will be raised when python[1] is called.
        json_query = json.dumps({'query': {'filter': ['not']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[0] is called.
        json_query = json.dumps({'query': {'filter': []}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[1] is called.
        json_query = json.dumps({'query': {'filter': ['and']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['IndexError'] == u'list index out of range'

        # TypeError bad num args will be triggered when _get_simple_filter_expression is
        # called on a string whose len is not 4, i.e., 'id' or '='.
        json_query = json.dumps({'query': {'filter': ['and', ['File', 'id', '=', '1099']]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'TypeError' in resp['errors']
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # TypeError when asking whether [] is in a dict (lists are unhashable)
        json_query = json.dumps({'query': {'filter': [[], 'a', 'a', 'a']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['TypeError'] == u"unhashable type: 'list'"
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # With no 'query' attribute, the SQLAQueryBuilder will be passed None and
        # will immediately raise an AttributeError.
        json_query = json.dumps({'filter': ['File', 'id', '=', 2]})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

        # With no 'filter' attribute, the SQLAQueryBuilder will be passed a list
        # will immediately raise an AttributeError when it tries to call [...].get('filter').
        json_query = json.dumps({'query': ['File', 'id', '=', 2]})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    @nottest
    def test_search_l_lexical_semantic_error(self):
        """Tests POST /files/search: lexical & semantic errors.

        These are when SQLAQueryBuilder.py raises a OLDSearchParseError because a
        relation is not permitted, e.g., 'contains', or not permitted for a
        given attribute.
        """

        # search_parser.py does not allow the contains relation (OLDSearchParseError)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'name', 'contains', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'File.name.contains' in resp['errors']

        # model.File.tags.__eq__('abcdefg') will raise a custom OLDSearchParseError
        json_query = json.dumps(
            {'query': {'filter': ['File', 'tags', '=', u'abcdefg']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

        # model.File.tags.regexp('xyz') will raise a custom OLDSearchParseError
        json_query = json.dumps({'query': {'filter': ['File', 'tags', 'regex', u'xyz']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['File.tags.regex'] == u'The relation regex is not permitted for File.tags'

        # model.File.tags.like('name') will raise a custom OLDSearchParseError
        json_query = json.dumps({'query': {'filter': ['File', 'tags', 'like', u'abc']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.tags.like'] == \
            u'The relation like is not permitted for File.tags'

        # model.File.tags.__eq__('tag') will raise a custom OLDSearchParseError
        json_query = json.dumps({'query': {'filter': ['File', 'tags', '__eq__', u'tag']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'InvalidRequestError' in resp['errors']

    @nottest
    def test_search_m_conjunction(self):
        """Tests SEARCH /files: conjunction."""
        users = h.get_users()
        contributor = [u for u in users if u.role == u'contributor'][0]
        models = self._get_test_models()
        files = [f.get_dict() for f in h.get_files()]

        # 1 conjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'and', [
                ['File', 'name', 'like', u'%2%']
            ]
        ]}}
        json_query = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'2' in f['name']]
        assert len(resp) == len(result_set)

        # 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['File', 'name', 'like', u'%2%'],
                ['File', 'name', 'like', u'%1%']
            ]
        ]}}
        json_query = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'2' in f['name'] and u'1' in f['name']]
        assert len(resp) == len(result_set)
        assert sorted([f['name'] for f in resp]) == sorted([f['name'] for f in result_set])

        # More than 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['File', 'name', 'like', u'%1%'],
                ['File', 'elicitor', 'id', '=', contributor.id],
                ['File', 'speaker', 'id', '=', models['speakers'][3]['id']]
            ]
        ]}}
        json_query = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'1' in f['name'] and
                     (f['elicitor'] and f['elicitor']['id'] == contributor.id) and
                     (f['speaker'] and f['speaker']['id'] == models['speakers'][3]['id'])]
        assert len(resp) == len(result_set)
        assert sorted([f['name'] for f in resp]) == sorted([f['name'] for f in result_set])

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
        json_query = json.dumps(query)
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'1' in f['name']]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_n_disjunction(self):
        """Tests POST /files/search: disjunction."""
        users = h.get_users()
        contributor = [u for u in users if u.role == u'contributor'][0]
        files = [f.get_dict() for f in h.get_files()]

        # 1 disjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'or', [
                ['File', 'name', 'like', u'%2%']   # 19 total
            ]
        ]}}
        json_query = json.dumps(query)
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'2' in f['name']]
        assert len(resp) == len(result_set)

        # 2 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['File', 'name', 'like', u'%2%'],
                ['File', 'name', 'like', u'%1%']
            ]
        ]}}
        json_query = json.dumps(query)
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'2' in f['name'] or u'1' in f['name']]
        assert len(resp) == len(result_set)

        # 3 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['File', 'name', 'like', u'%2%'],
                ['File', 'name', 'like', u'%1%'],
                ['File', 'elicitor', 'id', '=', contributor.id]
            ]
        ]}}
        json_query = json.dumps(query)
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if u'2' in f['name'] or u'1' in f['name']
                     or (f['elicitor'] and f['elicitor']['id'] == contributor.id)]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_o_int(self):
        """Tests SEARCH /files: integer searches."""

        files = [f.get_dict() for f in h.get_files()]
        file_ids = [f['id'] for f in files]

        # = int
        json_query = json.dumps({'query': {'filter': ['File', 'id', '=', file_ids[1]]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['id'] == file_ids[1]

        # < int (str)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'id', '<', str(file_ids[16])]}}) # Thanks to SQLAlchemy, a string will work here too
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['id'] < file_ids[16]]
        assert len(resp) == len(result_set)

        # >= int
        json_query = json.dumps({'query': {'filter': ['File', 'id', '>=', file_ids[9]]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['id'] >= file_ids[9]]
        assert len(resp) == len(result_set)

        # in array
        json_query = json.dumps(
            {'query': {'filter':
                ['File', 'id', 'in', [file_ids[1], file_ids[3], file_ids[8], file_ids[19]]]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4
        assert sorted([f['id'] for f in resp]) == [file_ids[1], file_ids[3], file_ids[8], file_ids[19]]

        # in None -- Error
        json_query = json.dumps({'query': {'filter': ['File', 'id', 'in', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.id.in_'] == u"Invalid filter expression: File.id.in_(None)"

        # in int -- Error
        json_query = json.dumps({'query': {'filter': ['File', 'id', 'in', 2]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.id.in_'] == u"Invalid filter expression: File.id.in_(2)"

        # regex int - The OLD's Python-based regexp implementation for SQLite will
        # automatically convert a non-string field value to a string before doing
        # the regexp comparison.  I believe that this parallels MySQL's regexp
        # behaviour accurately.
        str_patt = u'[12][12]'
        patt = re.compile(str_patt)
        expected_id_matches = [f['id'] for f in files if patt.search(str(f['id']))]
        json_query = json.dumps({'query': {'filter': ['File', 'id', 'regex', str_patt]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expected_id_matches)
        assert sorted([f['id'] for f in resp]) == sorted(expected_id_matches)

        # like int - RDBMS treats ints as strings for LIKE search
        json_query = json.dumps({'query': {'filter': ['File', 'id', 'like', u'%2%']}})
        expected_matches = [i for i in file_ids if u'2' in str(i)]
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expected_matches)

    @nottest
    def test_search_p_date(self):
        """Tests POST /files/search: date searches."""
        files = [f.get_dict() for f in h.get_files()]

        # = date
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '=', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if isofy(f['date_elicited']) == jan1.isoformat()]
        assert len(resp) == len(result_set)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '=', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if isofy(f['date_elicited']) == jan3.isoformat()]
        assert len(resp) == len(result_set)

        # != date -- *NOTE:* the NULL date_elicited values will not be counted.
        # The implicit query is 'is not null and != 2012-01-01'
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '!=', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if isofy(f['date_elicited']) is not None and
                     isofy(f['date_elicited']) != jan1.isoformat()]
        assert len(resp) == len(result_set)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '!=', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if isofy(f['date_elicited']) is not None and
                     isofy(f['date_elicited']) != jan3.isoformat()]
        assert len(resp) == len(result_set)

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter': [
            'or', [['File', 'date_elicited', '!=', jan1.isoformat()],
                ['File', 'date_elicited', '=', None]]]}}
        json_query = json.dumps(query)
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if isofy(f['date_elicited']) != jan1.isoformat()]
        assert len(resp) == len(result_set)

        # < date
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '<', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and f['date_elicited'] < jan1]
        assert len(resp) == len(result_set)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '<', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and f['date_elicited'] < jan3]
        assert len(resp) == len(result_set)

        # <= date
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '<=', jan3.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and f['date_elicited'] <= jan3]
        assert len(resp) == len(result_set)

        # > date
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '>', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and f['date_elicited'] > jan2]
        assert len(resp) == len(result_set)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '>', '0001-01-01']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and
                     isofy(f['date_elicited']) > '0001-01-01']
        assert len(resp) == len(result_set)

        # >= date
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '>=', jan1.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and f['date_elicited'] >= jan1]
        assert len(resp) == len(result_set)

        # =/!= None
        json_query = json.dumps({'query': {'filter': ['File', 'date_elicited', '=', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is None]
        assert len(resp) == len(result_set)

        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '__ne__', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_q_date_invalid(self):
        """Tests SEARCH /files: invalid date searches."""

        files = [f.get_dict() for f in h.get_files()]

        # = invalid date
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '=', '12-01-01']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 12-01-01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', '=', '2012-01-32']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 2012-01-32'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on invalid date will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', 'regex', '01']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on valid date will work and will act just like = -- no point
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', 'regex', '2012-01-01']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and
                     f['date_elicited'].isoformat() == '2012-01-01']
        assert len(resp) == len(result_set)

        # Same thing for like, it works like = but what's the point?
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', 'like', '2012-01-01']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(result_set)

        # in_ on a date.  This will raise a TypeError ('datetime.date' object is
        # not iterable) that is caught in _get_filter_expression
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', 'in', '2012-01-02']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.date_elicited.in_'] == u'Invalid filter expression: File.date_elicited.in_(datetime.date(2012, 1, 2))'

        # in_ on a list of dates works (SQLAQueryBuilder generates a list of date objects)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'date_elicited', 'in', ['2012-01-01', '2012-01-03']]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['date_elicited'] is not None and
                     f['date_elicited'].isoformat() in ['2012-01-01', '2012-01-03']]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_r_datetime(self):
        """Tests POST /files/search: datetime searches."""
        files = [f.get_dict() for f in h.get_files()]

        # = datetime
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '=', today_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] == today_timestamp]
        assert len(resp) == len(result_set)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '=', yesterday_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] == yesterday_timestamp]
        assert len(resp) == len(result_set)

        # != datetime -- *NOTE:* the NULL datetime_entered values will not be counted.
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '!=', today_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] != today_timestamp]
        assert len(resp) == len(result_set)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '!=', yesterday_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] != yesterday_timestamp]
        assert len(resp) == len(result_set)

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter':
            ['or', [['File', 'datetime_entered', '!=', today_timestamp.isoformat()],
                ['File', 'datetime_entered', '=', None]]]}}
        json_query = json.dumps(query)
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is None or
                     f['datetime_entered'] != today_timestamp]
        assert len(resp) == len(result_set)

        # < datetime
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '<', today_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'] < today_timestamp]
        assert len(resp) == len(result_set)

        # <= datetime
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '<=', today_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'] <= today_timestamp]
        assert len(resp) == len(result_set)

        # > datetime
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '>', today_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'] > today_timestamp]
        assert len(resp) == len(result_set)
        # Note: Python2.6/Debian(?) bug: using a year before 1900 will cause problems: 
        # ValueError: year=1 is before 1900; the datetime strftime() methods require year >= 1900
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '>', '1901-01-01T09:08:07']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'].isoformat() > '1901-01-01T09:08:07']
        assert len(resp) == len(result_set)

        # >= datetime
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '>=', yesterday_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'] >= yesterday_timestamp]
        assert len(resp) == len(result_set)

        # =/!= None
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '=', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is None]
        assert len(resp) == len(result_set)

        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_entered', '__ne__', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None]
        assert len(resp) == len(result_set)

        # datetime in today
        midnight_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        midnight_tomorrow = midnight_today + day_delta
        query = {'query': {'filter':
            ['and', [['File', 'datetime_entered', '>', midnight_today.isoformat()],
                         ['File', 'datetime_entered', '<', midnight_tomorrow.isoformat()]]]}}
        json_query = json.dumps(query)
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'] > midnight_today and
                     f['datetime_entered'] < midnight_tomorrow]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_s_datetime_invalid(self):
        """Tests SEARCH /files: invalid datetime searches."""
        files = [f.get_dict() for f in h.get_files()]

        # = invalid datetime
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_modified', '=', '12-01-01T09']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 12-01-01T09'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_modified', '=', '2012-01-30T09:08:61']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 2012-01-30T09:08:61'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # Trailing period and too many microseconds will both succeed.
        json_query = json.dumps({'query': {'filter':
                ['File', 'datetime_modified', '=', '2012-01-30T09:08:59.123456789123456789123456789']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        json_query = json.dumps({'query': {'filter':
            ['File', 'datetime_modified', '=', '2012-01-30T09:08:59.']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)

        # regex on invalid datetime will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        json_query = json.dumps(
            {'query': {'filter': ['File', 'datetime_modified', 'regex', '01']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 01'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # regex on valid datetime will work and will act just like = -- no point
        json_query = json.dumps({'query': {'filter':
                ['File', 'datetime_entered', 'regex', today_timestamp.isoformat()]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'] == today_timestamp]
        assert len(resp) == len(result_set)

        # Same thing for like, it works like = but what's the point?
        json_query = json.dumps({'query': {'filter':
                ['File', 'datetime_modified', 'like', today_timestamp.isoformat()]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_entered'] is not None and
                     f['datetime_entered'] == today_timestamp]
        assert len(resp) == len(result_set)

        # in_ on a datetime.  This will raise a TypeError ('datetime.datetime' object is
        # not iterable) that is caught in _get_filter_expression
        json_query = json.dumps({'query': {'filter':
            ['File', 'datetime_modified', 'in', today_timestamp.isoformat()]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.datetime_modified.in_'].startswith(
            u'Invalid filter expression: File.datetime_modified.in_')

        # in_ on a list of datetimes works (SQLAQueryBuilder generates a list of datetime objects)
        json_query = json.dumps({'query': {'filter':
            ['File', 'datetime_modified', 'in',
                [today_timestamp.isoformat(), yesterday_timestamp.isoformat()]]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['datetime_modified'] is not None and
                     f['datetime_modified'] in (today_timestamp, yesterday_timestamp)]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_t_many_to_one(self):
        """Tests POST /files/search: searches on many-to-one attributes."""
        files = [f.get_dict() for f in h.get_files()]

        test_models = self._get_test_models()
        users = h.get_users()
        contributor = [u for u in users if u.role == u'contributor'][0]

        # = int
        json_query = json.dumps(
            {'query': {'filter': ['File', 'enterer', 'id', '=', contributor.id]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['enterer']['id'] == contributor.id]
        assert len(resp) == len(result_set)

        json_query = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', '=', test_models['speakers'][0]['id']]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['speaker'] and
                     f['speaker']['id'] == test_models['speakers'][0]['id']]
        assert len(resp) == len(result_set)

        # in array of ints
        json_query = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'in', [s['id'] for s in test_models['speakers']]]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['speaker'] and
                     f['speaker']['id'] in [s['id'] for s in test_models['speakers']]]
        assert len(resp) == len(result_set)

        # <
        json_query = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', '<', 15]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['speaker'] and
                     f['speaker']['id'] < 15]
        assert len(resp) == len(result_set)

        # regex
        json_query = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'regex', '5']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['speaker'] and
                     u'5' in str(f['speaker']['id'])]
        assert len(resp) == len(result_set)

        json_query = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'regex', '[56]']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['speaker'] and
                     re.search('[56]', str(f['speaker']['id']))]
        assert len(resp) == len(result_set)

        # like
        json_query = json.dumps({'query': {'filter':
            ['File', 'speaker', 'id', 'like', '%5%']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['speaker'] and
                     '5' in str(f['speaker']['id'])]
        assert len(resp) == len(result_set)

        # regex on parent_file.filename
        json_query = json.dumps({'query': {'filter':
            ['File', 'parent_file', 'filename', 'regex', '[13579]']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['parent_file'] and
                     set(list('13579')) & set(list(f['parent_file']['filename']))]
        assert len(resp) == len(result_set)

    @nottest
    def test_search_v_many_to_many(self):
        """Tests POST /files/search: searches on many-to-many attributes, i.e., Tag, Form."""
        files = [f.get_dict() for f in h.get_files()]

        # tag.name =
        json_query = json.dumps({'query': {'filter': ['Tag', 'name', '=', 'name_6.jpg']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if 'name_6.jpg' in [t['name'] for t in f['tags']]]
        assert len(resp) == len(result_set)

        # tag.name = (using any())
        json_query = json.dumps({'query': {'filter': ['File', 'tags', 'name', '=', 'name_6.jpg']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(result_set)

        # form.transcription like
        json_query = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'like', '%transcription 6%']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files
                     if 'transcription 6' in ''.join([fo['transcription'] for fo in f['forms']])]
        assert len(resp) == len(result_set)

        # form.transcription regexp
        json_query = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'regex', 'transcription [12]']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files
                     if re.search('transcription [12]', ''.join([fo['transcription'] for fo in f['forms']]))]
        assert len(resp) == len(result_set)

        # tag.name in_
        names = [u'name 77', u'name 79', u'name 99']
        json_query = json.dumps({'query': {'filter':
            ['Tag', 'name', 'in_', names]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if set(names) & set([t['name'] for t in f['tags']])]
        assert len(resp) == len(result_set)

        # tag.name <
        json_query = json.dumps({'query': {'filter':
            ['Tag', 'name', '<', u'name 2']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if [t for t in f['tags'] if t['name'] < u'name 2']]
        assert len(resp) == len(result_set)

        # form.datetime_entered
        json_query = json.dumps({'query': {'filter':
            ['Form', 'datetime_entered', '>', yesterday_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files
                     if [fo for fo in f['forms'] if fo['datetime_entered'] > yesterday_timestamp]]
        assert len(resp) == len(result_set)

        json_query = json.dumps({'query': {'filter':
            ['Form', 'datetime_entered', '<', yesterday_timestamp.isoformat()]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files
                     if [fo for fo in f['forms'] if fo['datetime_entered'] < yesterday_timestamp]]
        assert len(resp) == len(result_set)

        # To search for the presence/absence of tags/forms, one must use the
        # tags/forms attributes of the File model.
        json_query = json.dumps({'query': {'filter': ['File', 'tags', '=', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if not f['tags']]
        assert len(resp) == len(result_set)

        json_query = json.dumps({'query': {'filter': ['File', 'forms', '!=', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['forms']]
        assert len(resp) == len(result_set)

        # Using anything other than =/!= on Form.tags/files/collections will raise an error.
        json_query = json.dumps({'query': {'filter': ['File', 'tags', 'like', None]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.tags.like'] == u'The relation like is not permitted for File.tags'

        json_query = json.dumps({'query': {'filter':
            ['File', 'forms', '=', 'form 2']}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

    @nottest
    def test_search_w_in(self):
        """Tests SEARCH /files: searches using the in_ relation."""
        files = [f.get_dict() for f in h.get_files()]

        # Array value -- all good.
        json_query = json.dumps({'query': {'filter':
            ['File', 'name', 'in', ['name_1.jpg']]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if f['name'] in ['name_1.jpg']]
        assert len(resp) == len(result_set)

        # String value -- no error because strings are iterable; but no results
        json_query = json.dumps({'query': {'filter':
            ['File', 'name', 'in', 'name_1.jpg']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0

    @nottest
    def test_search_x_complex(self):
        """Tests POST /files/search: complex searches."""
        files = [f.get_dict() for f in h.get_files()]

        # A fairly complex search
        json_query = json.dumps({'query': {'filter': [
            'and', [
                ['Tag', 'name', 'like', '%1%'],
                ['not', ['File', 'name', 'regex', '[12][5-7]']],
                ['or', [
                    ['File', 'datetime_entered', '>', today_timestamp.isoformat()],
                    ['File', 'date_elicited', '>', jan1.isoformat()]]]]]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if
            '1' in ' '.join([t['name'] for t in f['tags']]) and
            not re.search('[12][5-7]', f['name']) and
            (today_timestamp < f['datetime_entered'] or
            (f['date_elicited'] and jan1 < f['date_elicited']))]
        assert len(resp) == len(result_set)

        # A complex search entailing multiple joins
        tag_names = ['name 2', 'name 4', 'name 8']
        patt = '([13579][02468])|([02468][13579])'
        json_query = json.dumps({'query': {'filter': [
            'or', [
                ['Form', 'transcription', 'like', '%1%'],
                ['Tag', 'name', 'in', tag_names],
                ['and', [
                    ['not', ['File', 'name', 'regex', patt]],
                    ['File', 'date_elicited', '!=', None]]]]]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if
            '1' in ' '.join([fo['transcription'] for fo in f['forms']]) or
            set([t['name'] for t in f['tags']]) & set(tag_names) or
            (not re.search(patt, f['name']) and
             f['date_elicited'] is not None)]
        assert len(resp) == len(result_set)

        # A complex search ...  The implicit assertion is that a 200 status
        # code is returned.  At this point I am not going to bother attempting to
        # emulate this query in Python ...
        json_query = json.dumps({'query': {'filter': [
            'and', [
                ['File', 'name', 'like', '%5%'],
                ['File', 'description', 'regex', '.'],
                ['not', ['Tag', 'name', 'like', '%6%']],
                ['or', [
                    ['File', 'datetime_entered', '<', today_timestamp.isoformat()],
                    ['not', ['File', 'date_elicited', 'in', [jan1.isoformat(), jan3.isoformat()]]],
                    ['and', [
                        ['File', 'enterer', 'id', 'regex', '[135680]'],
                        ['File', 'id', '<', 90]
                    ]]
                ]],
                ['not', ['not', ['not', ['Tag', 'name', '=', 'name 7']]]]
            ]
        ]}})
        response = self.app.post(url('/files/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

    @nottest
    def test_search_y_paginator(self):
        """Tests SEARCH /files: paginator."""
        files = json.loads(json.dumps(h.get_files(), cls=h.JSONOLDEncoder))

        # A basic search with a paginator provided.
        json_query = json.dumps(
            {'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'page': 2, 'items_per_page': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [f for f in files if 'N' in f['name']]
        assert resp['paginator']['count'] == len(result_set)
        assert len(resp['items']) == 3
        assert resp['items'][0]['id'] == result_set[3]['id']
        assert resp['items'][-1]['id'] == result_set[5]['id']

        # An invalid paginator (here 'page' is less than 1) will result in formencode.Invalid
        # being raised resulting in a response with a 400 status code and a JSON error msg.
        json_query = json.dumps({
            'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'page': 0, 'items_per_page': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

        # Some "invalid" paginators will silently fail.  For example, if there is
        # no 'pages' key, then GET /files will just assume there is no paginator
        # and all of the results will be returned.
        json_query = json.dumps({
            'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'pages': 0, 'items_per_page': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len([f for f in files if 'N' in f['name']])

        # Adding a 'count' key to the paginator object in the request will spare
        # the server from running query.count().  Note that the server will not
        # attempt to verify the count (since that would defeat the purpose) but
        # will simply pass it back.  The server trusts that the client is passing
        # in a factual count.  Here we pass in an inaccurate count for demonstration.
        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'like', '%N%']},
            'paginator': {'page': 2, 'items_per_page': 4, 'count': 750}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['paginator']['count'] == 750
        assert len(resp['items']) == 4
        assert resp['items'][0]['id'] == result_set[4]['id']
        assert resp['items'][-1]['id'] == result_set[7]['id']

    @nottest
    def test_search_z_order_by(self):
        """Tests POST /files/search: order by."""
        files = json.loads(json.dumps(h.get_files(), cls=h.JSONOLDEncoder))

        # order by name ascending
        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'order_by': ['File', 'name', 'asc']}})
        response = self.app.post(url('/files/search'), json_query,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_9.jpg'
        assert resp[0]['name'] == u'name_1.jpg'

        # order by name descending
        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'order_by': ['File', 'name', 'desc']}})
        response = self.app.post(url('/files/search'), json_query,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_1.jpg'
        assert resp[0]['name'] == u'name_9.jpg'

        # order by with missing direction defaults to 'asc'
        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'order_by': ['File', 'name']}})
        response = self.app.post(url('/files/search'), json_query,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_9.jpg'
        assert resp[0]['name'] == u'name_1.jpg'

        # order by with unknown direction defaults to 'asc'
        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'order_by': ['File', 'name', 'descending']}})
        response = self.app.post(url('/files/search'), json_query,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(files)
        assert resp[-1]['name'] == u'name_9.jpg'
        assert resp[0]['name'] == u'name_1.jpg'

        # syntactically malformed order by
        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'order_by': ['File']}})
        response = self.app.post(url('/files/search'), json_query,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        # searches with lexically malformed order bys
        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'order_by': ['File', 'foo', 'desc']}})
        response = self.app.post(url('/files/search'), json_query,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['File.foo'] == u'Searching on File.foo is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        json_query = json.dumps({'query': {
                'filter': ['File', 'name', 'regex', '[nN]'],
                'order_by': ['Foo', 'id', 'desc']}})
        response = self.app.post(url('/files/search'), json_query,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Foo'] == u'Searching the File model by joining on the Foo model is not possible'
        assert resp['errors']['Foo.id'] == u'Searching on Foo.id is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

    @nottest
    def test_search_za_restricted(self):
        """Tests SEARCH /files: restricted files."""

        # First restrict the even-numbered forms
        restricted_tag = h.generate_restricted_tag()
        Session.add(restricted_tag)
        Session.commit()
        restricted_tag = h.get_restricted_tag()
        files = h.get_files()
        file_count = len(files)
        for file in files:
            if int(file.name.split('_')[-1].split('.')[0]) % 2 == 0:
                file.tags.append(restricted_tag)
        Session.commit()
        restricted_files = Session.query(model.File).filter(
            model.Tag.name==u'restricted').outerjoin(model.File.tags).all()
        restricted_file_count = len(restricted_files)

        # A viewer will only be able to see the unrestricted files
        json_query = json.dumps({'query': {'filter':
            ['File', 'name', 'regex', '[nN]']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == restricted_file_count
        assert 'restricted' not in [
            x['name'] for x in reduce(list.__add__, [f['tags'] for f in resp])]

        # An administrator will be able to access all files
        json_query = json.dumps({'query': {'filter':
            ['File', 'name', 'regex', '[nN]']}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == file_count
        assert 'restricted' in [
            x['name'] for x in reduce(list.__add__, [f['tags'] for f in resp])]

        # Filter out restricted files and do pagination
        json_query = json.dumps({'query': {'filter':
            ['File', 'name', 'regex', '[nN]']},
            'paginator': {'page': 2, 'items_per_page': 3}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_view)
        resp = json.loads(response.body)
        result_set = [f for f in files
                        if int(f.name.split('_')[-1].split('.')[0]) % 2 != 0]
        assert resp['paginator']['count'] == restricted_file_count
        assert len(resp['items']) == 3
        assert resp['items'][0]['id'] == result_set[3].id

    @nottest
    def test_search_zb_file_type(self):
        """Tests SEARCH /files: get the different types of files."""
        # Get all files with real files to back them up, (they're the ones with filenames).
        json_query = json.dumps({'query': {'filter': ['File', 'filename', '!=', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 30

        # Get all the subinterval-referencing.
        json_query = json.dumps({'query': {'filter': ['File', 'parent_file', '!=', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 10

        # Get all the subinterval-referencing.
        json_query = json.dumps({'query': {'filter': ['File', 'url', '!=', None]}})
        response = self.app.request(url('files'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 10

    @nottest
    def test_z_cleanup(self):
        """Tests POST /files/search: clean up the database."""

        h.clear_all_models()
        administrator = h.generate_default_administrator()
        contributor = h.generate_default_contributor()
        viewer = h.generate_default_viewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        # Perform a vacuous GET just to delete app_globals.application_settings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.application_settings'] = True
        self.app.get(url('files'), extra_environ=extra_environ)

        # Remove all of the binary (file system) files created.
        h.clear_directory_of_files(self.files_path)
        h.clear_directory_of_files(self.reduced_files_path)
