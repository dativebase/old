"""This module tests the form search functionality, i.e., requests to SEARCH
/forms and POST /forms/search.

NOTE: getting the non-standard http SEARCH method to work in the tests required
using the request method of TestController().app and specifying values for the
method, body, headers, and environ kwarg parameters.  WebTest prints a
WSGIWarning when unknown HTTP methods (e.g., SEARCH) are used.  To prevent this,
I altered the global valid_methods tuple of webtest.lint at runtime by adding a
'SEARCH' method (see addSEARCHToWebTestValidMethods() below).
"""

import re
from old.tests import *
from nose.tools import nottest
import simplejson as json
import logging
from datetime import date, datetime, timedelta
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h
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
def createTestModels(n=100):
    addTestModelsToSession('Tag', n, ['name'])
    addTestModelsToSession('Speaker', n, ['firstName', 'lastName', 'dialect'])
    addTestModelsToSession('Source', n, ['authorFirstName', 'authorLastName',
                                            'title'])
    addTestModelsToSession('ElicitationMethod', n, ['name'])
    addTestModelsToSession('SyntacticCategory', n, ['name'])
    addTestModelsToSession('File', n, ['name'])
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
    users = h.getUsers()
    viewer = [u for u in users if u.role == u'viewer'][0]
    contributor = [u for u in users if u.role == u'contributor'][0]
    administrator = [u for u in users if u.role == u'administrator'][0]
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
        g = model.Gloss()
        g.gloss = u'gloss %d' % i
        f.enterer = contributor
        f.syntacticCategory = testModels['syntacticCategories'][i - 1]
        if i > 75:
            f.phoneticTranscription = u'phoneticTranscription %d' % i
            f.narrowPhoneticTranscription = u'narrowPhoneticTranscription %d' % i
            t = testModels['tags'][i - 1]
            f.tags.append(t)
            g.glossGrammaticality = u'*'
        if i > 65 and i < 86:
            fi = testModels['files'][i - 1]
            f.files.append(fi)
        if i > 50:
            f.elicitor = contributor
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
            f.glosses.append(g)
        if i == 79:
            g = model.Gloss()
            g.gloss = u'gloss %d the second' % i
            f.glosses.append(g)
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


class TestFormsSearchController(TestController):

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    extra_environ_viewer = {'test.authentication.role': u'viewer'}
    json_headers = {'Content-Type': 'application/json'}
    n = 100

    # Clear all models in the database except Language; recreate the users.
    def tearDown(self):
        pass

    # There are 24 distinct forms search tests (a-x).  Aside from the
    # requirement that the initialize "test" needs to run first, these create
    # tests do not need to be executed in the order determined by their names;
    # it just helps in locating them.
    #@nottest
    def test_a_initialize(self):
        """Tests POST /forms/search: initialize database."""
        # Add a bunch of data to the db.
        createTestData(self.n)
        addSEARCHToWebTestValidMethods()

    #@nottest
    def test_search_b_equals(self):
        """Tests POST /forms/search: equals."""
        # Simple == search on transcriptions
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', '=', 'transcription 10']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['transcription'] == u'transcription 10'

    #@nottest
    def test_search_c_not_equals(self):
        """Tests SEARCH /forms: not equals."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Form', 'transcription', '=', u'transcription 10']]}})
        response = self.app.request(url('forms'), method='SEARCH',
            body=jsonQuery, headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == self.n - 1
        assert u'transcription 10' not in [f['transcription'] for f in resp]

    #@nottest
    def test_search_d_like(self):
        """Tests POST /forms/search: like."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'like', u'%1%']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20  # 1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 31, 41, 51, 61, 71, 81, 91, 100

        # Case-sensitive like.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'like', u'%T%']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        jsonQuery = json.dumps(
            {'query': {'filter': ['or', [
                ['Form', 'transcription', 'like', u'T%'],
                ['Form', 'transcription', 'like', u't%']]]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100

    #@nottest
    def test_search_e_not_like(self):
        """Tests SEARCH /forms: not like."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Form', 'transcription', 'like', u'%1%']]}})
        response = self.app.request(url('forms'), method='SEARCH',
            body=jsonQuery, headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 80

    #@nottest
    def test_search_f_regexp(self):
        """Tests POST /forms/search: regular expression."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'regex', u'[345]2']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert sorted([f['transcription'] for f in resp]) == \
            [u'TRANSCRIPTION 52', u'transcription 32', u'transcription 42']
        assert len(resp) == 3  # 32, 42, 52

        # Case-sensitive regexp.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'regex', u'^T']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'regex', u'^[Tt]']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100

        # Beginning and end of string anchors
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'regex', u'^[Tt]ranscription 1.$']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 10

        # Quantifiers
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'regex', u'2{2,}']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Quantifiers
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'regex', u'[123]{2,}']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 9

        # Bad regex
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'regex', u'[123]{3,2}']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    #@nottest
    def test_search_g_not_regexp(self):
        """Tests SEARCH /forms: not regular expression."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Form', 'transcription', 'regexp', u'[345]2']]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 97

    #@nottest
    def test_search_h_empty(self):
        """Tests POST /forms/search: is NULL."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'narrowPhoneticTranscription', '=', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # Same as above but with a double negative
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Form', 'narrowPhoneticTranscription', '!=', None]]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

    #@nottest
    def test_search_i_not_empty(self):
        """Tests SEARCH /forms: is not NULL."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Form', 'narrowPhoneticTranscription', '=', None]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

        # Same as above, but with !=, i.e., __ne__
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'narrowPhoneticTranscription', '!=', None]}})
        response = self.app.request(url('forms'), body=jsonQuery, method='SEARCH',
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

    #@nottest
    def test_search_j_invalid_json(self):
        """Tests POST /forms/search: invalid JSON params."""
        jsonQuery = json.dumps(
            {'query': {'filter': ['not', ['Form', 'narrowPhoneticTranscription', '=', None]]}})
        jsonQuery = jsonQuery[:-1]  # Cut off the end to make it bad!
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'JSON decode error: the parameters provided were not valid JSON.'

    #@nottest
    def test_search_k_malformed_query(self):
        """Tests SEARCH /forms: malformed query."""

        # TypeError - bad num args: 'NOT' will be treated as the first arg to
        # _getSimpleFilterExpression and ['Form', 'transcription', '=', 10] will be passed
        # as the second -- two more are required.
        jsonQuery = json.dumps({'query': {'filter': ['NOT', ['Form', 'id', '=', 10]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # After recognizing 'not', the query builder will look at only the next
        # list and ignore all the rest.
        jsonQuery = json.dumps(
            {'query': {'filter':
                ['not',
                    ['Form', 'transcription', '=', 'transcription 10'], 
                    ['Form', 'transcription', '=', 'transcription 10'],
                    ['Form', 'transcription', '=', 'transcription 10']]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99
        assert 'transcription 10' not in [f['transcription'] for f in resp]

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps({'query': {'filter': ['not']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[0] is called.
        jsonQuery = json.dumps({'query': {'filter': []}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps({'query': {'filter': ['and']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['IndexError'] == u'list index out of range'

        # TypeError bad num args will be triggered when _getSimpleFilterExpression is
        # called on a string whose len is not 4, i.e., 'id' or '='.
        jsonQuery = json.dumps({'query': {'filter': ['and', ['Form', 'id', '=', '1099']]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'TypeError' in resp['errors']
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # TypeError when asking whether [] is in a dict (lists are unhashable)
        jsonQuery = json.dumps({'query': {'filter': [[], 'a', 'a', 'a']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['TypeError'] == u"unhashable type: 'list'"
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # With no 'query' attribute, the SQLAQueryBuilder will be passed None
        # will immediately raise an AttributeError.
        jsonQuery = json.dumps({'filter': ['Form', 'id', '=', 2]})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

        # With no 'filter' attribute, the SQLAQueryBuilder will be passed a list
        # will immediately raise an AttributeError when it tries to call [...].get('filter').
        jsonQuery = json.dumps({'query': ['Form', 'id', '=', 2]})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The specified search parameters generated an invalid database query'

    #@nottest
    def test_search_l_lexical_semantic_error(self):
        """Tests POST /forms/search: lexical & semantic errors.

        These are when SQLAQueryBuilder.py raises a OLDSearchParseError because a
        relation is not permitted, e.g., 'contains', or not permitted for a
        given attribute.
        """

        # searchParser.py does not allow the contains relation (OLDSearchParseError)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'transcription', 'contains', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'Form.transcription.contains' in resp['errors']

        # model.Form.glosses.__eq__('abcdefg') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'glosses', '=', u'abcdefg']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

        # model.Form.tags.regexp('xyz') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'tags', 'regex', u'xyz']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['Form.tags.regex'] == u'The relation regex is not permitted for Form.tags'

        # model.Form.glosses.like('gloss') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'glosses', 'like', u'abc']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.glosses.like'] == \
            u'The relation like is not permitted for Form.glosses'

        # model.Form.tags.__eq__('tag') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'tags', '__eq__', u'tag']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'InvalidRequestError' in resp['errors']

    #@nottest
    def test_search_m_conjunction(self):
        """Tests SEARCH /forms: conjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]
        models = getTestModels()

        # 1 conjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'and', [
                ['Form', 'transcription', 'like', u'%2%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 19

        # 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['Form', 'transcription', 'like', u'%2%'],
                ['Form', 'transcription', 'like', u'%1%']
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert sorted([f['transcription'] for f in resp]) == ['transcription 12', 'transcription 21']

        # More than 2 conjuncts
        query = {'query': {'filter': [
            'and', [
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'elicitor', '=', contributor.id],
                ['Form', 'elicitationMethod', '=', models['elicitationMethods'][49].id]
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 3
        assert sorted([f['transcription'] for f in resp]) == \
            ['TRANSCRIPTION 51', 'TRANSCRIPTION 61', 'TRANSCRIPTION 71']

        # Multiple redundant conjuncts -- proof of possibility
        query = {'query': {'filter': [
            'and', [
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20

    #@nottest
    def test_search_n_disjunction(self):
        """Tests POST /forms/search: disjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]

        # 1 disjunct -- pointless, but it works...
        query = {'query': {'filter': [
            'or', [
                ['Form', 'transcription', 'like', u'%2%']   # 19 total
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 19

        # 2 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['Form', 'transcription', 'like', u'%2%'],    # 19; Total: 19
                ['Form', 'transcription', 'like', u'%1%']     # 18 (20 but '12' and '21' shared with '2'); Total: 37
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 37

        # 3 disjuncts
        query = {'query': {'filter': [
            'or', [
                ['Form', 'transcription', 'like', u'%2%'],    # 19; Total: 19
                ['Form', 'transcription', 'like', u'%1%'],    # 18 (20 but '12' and '21' shared with '2'); Total: 37
                ['Form', 'elicitor', '=', contributor.id]   # 39 (50 but 11 shared with '2' and '1'); Total: 76
            ]
        ]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 76

    #@nottest
    def test_search_o_int(self):
        """Tests SEARCH /forms: integer searches."""

        forms = h.getForms()
        formIds = [f.id for f in forms]

        # = int
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'id', '=', formIds[1]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['id'] == formIds[1]

        # < int (str)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'id', '<', str(formIds[16])]}}) # Thanks to SQLAlchemy, a string will work here too
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 16

        # >= int
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'id', '>=', formIds[97]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 3

        # in array
        jsonQuery = json.dumps(
            {'query': {'filter':
                ['Form', 'id', 'in', [formIds[12], formIds[36], formIds[28], formIds[94]]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4
        assert sorted([f['id'] for f in resp]) == [formIds[12], formIds[28], formIds[36], formIds[94]]

        # in None -- Error
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'id', 'in', None]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.id.in_'] == u"Invalid filter expression: Form.id.in_(None)"

        # in int -- Error
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'id', 'in', 2]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.id.in_'] == u"Invalid filter expression: Form.id.in_(2)"

        # regex int - The OLD's Python-based regexp implementation for SQLite will
        # automatically convert a non-string field value to a string before doing
        # the regexp comparison.  I believe that this parallels MySQL's regexp
        # behaviour accurately.
        strPatt = u'[13][58]'
        patt = re.compile(strPatt)
        expectedIdMatches = [f.id for f in forms if patt.search(str(f.id))]        
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'id', 'regex', u'[13][58]']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedIdMatches)
        assert sorted([f['id'] for f in resp]) == sorted(expectedIdMatches)

        # like int - RDBMS treats ints as strings for LIKE search
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'id', 'like', u'%2%']}})
        expectedMatches = [i for i in formIds if u'2' in str(i)]
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedMatches)

    #@nottest
    def test_search_p_date(self):
        """Tests POST /forms/search: date searches."""

        # = date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '=', jan1.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '=', jan4.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 23

        # != date -- *NOTE:* the NULL dateElicited values will not be counted.
        # The implicit query is 'is not null and != 2012-01-01'
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '!=', jan1.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 73
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '!=', jan4.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter': [
            'or', [['Form', 'dateElicited', '!=', jan1.isoformat()],
                ['Form', 'dateElicited', '=', None]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # < date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '<', jan1.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '<', jan3.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        # <= date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '<=', jan3.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # > date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '>', jan2.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 48
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '>', '0001-01-01']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 98

        # >= date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '>=', jan2.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 73

        # =/!= None
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'dateElicited', '=', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '__ne__', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 98

    #@nottest
    def test_search_q_date_invalid(self):
        """Tests SEARCH /forms: invalid date searches."""

        # = invalid date
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '=', '12-01-01']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 12-01-01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', '=', '2012-01-32']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 2012-01-32'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on invalid date will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', 'regex', '01']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on valid date will work and will act just like = -- no point
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', 'regex', '2012-01-01']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', 'like', '2012-01-01']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

        # in_ on a date.  This will raise a TypeError ('datetime.date' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', 'in', '2012-01-02']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.dateElicited.in_'] == u'Invalid filter expression: Form.dateElicited.in_(datetime.date(2012, 1, 2))'

        # in_ on a list of dates works (SQLAQueryBuilder generates a list of date objects)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'dateElicited', 'in', ['2012-01-01', '2012-01-02']]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

    #@nottest
    def test_search_r_datetime(self):
        """Tests POST /forms/search: datetime searches."""

        # = datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        # != datetime -- *NOTE:* the NULL datetimeEntered values will not be counted.
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '!=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '!=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # To get what one really wants (perhaps), test for NULL too:
        query = {'query': {'filter':
            ['or', [['Form', 'datetimeEntered', '!=', todayTimestamp.isoformat()],
                ['Form', 'datetimeEntered', '=', None]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 51

        # < datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '<', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        # <= datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeModified', '<=', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # > datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '>', todayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0
        # Note: Python2.6/Debian(?) bug: using a year before 1900 will cause problems: 
        # ValueError: year=1 is before 1900; the datetime strftime() methods require year >= 1900
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '>', '1901-01-01T09:08:07']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # >= datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '>=', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # =/!= None
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '=', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeEntered', '__ne__', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # datetime in today
        midnightToday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        midnightTomorrow = midnightToday + dayDelta
        query = {'query': {'filter':
            ['and', [['Form', 'datetimeEntered', '>', midnightToday.isoformat()],
                         ['Form', 'datetimeEntered', '<', midnightTomorrow.isoformat()]]]}}
        jsonQuery = json.dumps(query)
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

    #@nottest
    def test_search_s_datetime_invalid(self):
        """Tests SEARCH /forms: invalid datetime searches."""

        # = invalid datetime
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeModified', '=', '12-01-01T09']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 12-01-01T09'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeModified', '=', '2012-01-30T09:08:61']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 2012-01-30T09:08:61'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # Trailing period and too many microseconds will both succeed.
        jsonQuery = json.dumps({'query': {'filter':
                ['Form', 'datetimeModified', '=', '2012-01-30T09:08:59.123456789123456789123456789']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'datetimeModified', '=', '2012-01-30T09:08:59.']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)

        # regex on invalid datetime will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'datetimeModified', 'regex', '01']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 01'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # regex on valid datetime will work and will act just like = -- no point
        jsonQuery = json.dumps({'query': {'filter':
                ['Form', 'datetimeModified', 'regex', todayTimestamp.isoformat()]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps({'query': {'filter':
                ['Form', 'datetimeModified', 'like', todayTimestamp.isoformat()]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # in_ on a datetime.  This will raise a TypeError ('datetime.datetime' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'datetimeModified', 'in', todayTimestamp.isoformat()]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.datetimeModified.in_'] == \
            u'Invalid filter expression: Form.datetimeModified.in_(%s)' % repr(todayTimestamp)

        # in_ on a list of datetimes works (SQLAQueryBuilder generates a list of datetime objects)
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'datetimeModified', 'in',
                [todayTimestamp.isoformat(), yesterdayTimestamp.isoformat()]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

    #@nottest
    def test_search_t_many_to_one(self):
        """Tests POST /forms/search: searches on many-to-one attributes."""

        testModels = getTestModels()
        users = h.getUsers()
        forms = h.getForms()
        viewer = [u for u in users if u.role == u'viewer'][0]
        contributor = [u for u in users if u.role == u'contributor'][0]
        administrator = [u for u in users if u.role == u'administrator'][0]

        # = int
        jsonQuery = json.dumps(
            {'query': {'filter': ['Form', 'enterer', '=', contributor.id]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100

        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'speaker', '=', testModels['speakers'][0].id]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # in array of ints
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'speaker', 'in', [s.id for s in testModels['speakers']]]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # <
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'elicitationMethod', '<', 56]}})
        expectedForms = [f for f in forms if f.elicitationmethod_id < 56]
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

        # regex
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'elicitationMethod', 'regex', '5']}})
        expectedForms = [f for f in forms if '5' in str(f.elicitationmethod_id)]
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'elicitationMethod', 'regex', '[56]']}})
        expectedForms = [f for f in forms 
            if '5' in str(f.elicitationmethod_id) or '6' in str(f.elicitationmethod_id)] 
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

        # like
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'syntacticCategory', 'like', '%5%']}})
        expectedForms = [f for f in forms if '5' in str(f.syntacticcategory_id)]
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

    #@nottest
    def test_search_u_one_to_many(self):
        """Tests SEARCH /forms: searches on one-to-many attributes, viz. Gloss."""

        # gloss.gloss =
        jsonQuery = json.dumps({'query': {'filter':
            ['Gloss', 'gloss', '=', 'gloss 1']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # gloss.glossGrammaticality
        jsonQuery = json.dumps({'query': {'filter':
            ['Gloss', 'glossGrammaticality', '=', '*']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 24

        # gloss.gloss like
        jsonQuery = json.dumps({'query': {'filter':
            ['Gloss', 'gloss', 'like', '%1%']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20

        # gloss.gloss regexp
        jsonQuery = json.dumps({'query': {'filter':
            ['Gloss', 'gloss', 'regex', '[13][25]']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4

        # gloss.gloss in_
        jsonQuery = json.dumps({'query': {'filter':
            ['Gloss', 'gloss', 'in_', [u'gloss 1', u'gloss 2']]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # gloss.gloss <
        jsonQuery = json.dumps({'query': {'filter':
            ['Gloss', 'gloss', '<', u'z']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # gloss.datetimeModified
        jsonQuery = json.dumps({'query': {'filter':
            ['Gloss', 'datetimeModified', '>', yesterdayTimestamp.isoformat()]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # To search for the presence/absence of glosses, one must use the
        # glosses attribute of the Form model.
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'glosses', '=', None]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'glosses', '!=', None]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # Using anything other than =/!= on Form.glosses will raise an error.
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'glosses', 'like', None]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.glosses.like'] == u'The relation like is not permitted for Form.glosses'

        # Using a value other than None on Form.glosses will also raise an error
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'glosses', '=', 'gloss 1']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

        # Search based on two distinct glosses (only Form #79 has two)
        jsonQuery = json.dumps({'query': {'filter':
            ['and', [
                ['Gloss', 'gloss', '=', 'gloss 79'],
                ['Gloss', 'gloss', '=', 'gloss 79 the second']]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        # ... one is ungrammatical, the other is unspecified
        jsonQuery = json.dumps({'query': {'filter':
            ['and', [
                ['Gloss', 'glossGrammaticality', '=', '*'],
                ['Gloss', 'glossGrammaticality', '=', None]]]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

    #@nottest
    def test_search_v_many_to_many(self):
        """Tests POST /forms/search: searches on many-to-many attributes, i.e., Tag, File, Collection."""

        # tag.name =
        jsonQuery = json.dumps({'query': {'filter': ['Tag', 'name', '=', 'name 76']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # file.name like
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'like', '%name 6%']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4

        # file.name regexp
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'name', 'regex', 'name [67]']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 14

        # tag.name in_
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', 'in_', [u'name 77', u'name 79', u'name 99']]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 3

        # tag.name <
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', '<', u'name 8']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 5   # 76, 77, 78, 79, 100

        # file.datetimeModified
        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'datetimeModified', '>', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20  # All forms with a file attached

        jsonQuery = json.dumps({'query': {'filter':
            ['File', 'datetimeModified', '<', yesterdayTimestamp.isoformat()]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0

        # To search for the presence/absence of tags/files/collections, one must use the
        # tags/files/collections attributes of the Form model.
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'tags', '=', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        jsonQuery = json.dumps({'query': {'filter': ['Form', 'files', '!=', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20

        # Using anything other than =/!= on Form.tags/files/collections will raise an error.
        jsonQuery = json.dumps({'query': {'filter': ['Form', 'tags', 'like', None]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.tags.like'] == u'The relation like is not permitted for Form.tags'

        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'files', '=', 'file 80']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

        # tag.name in_ with double matches (Form #79 has Tags #78 and #79)
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', 'in_', [u'name 78', u'name 79']]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Form #79 has Tags #78 and #79
        jsonQuery = json.dumps({'query': {'filter':
            ['and', [
                ['Tag', 'name', '=', u'name 78'],
                ['Tag', 'name', '=', u'name 79']]]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Form #79 has Tags #78 and #79, Form #78 has Tag #78
        jsonQuery = json.dumps({'query': {'filter':
            ['Tag', 'name', '=', u'name 78']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

    #@nottest
    def test_search_w_in(self):
        """Tests SEARCH /forms: searches using the in_ relation."""

        # Array value -- all good.
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'in', ['transcription 1']]}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # String value -- no error because strings are iterable; but no results
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'in', 'transcription 1']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0

    #@nottest
    def test_search_x_complex(self):
        """Tests POST /forms/search: complex searches."""
        forms = json.loads(json.dumps(h.getForms(), cls=h.JSONOLDEncoder))

        # A fairly complex search
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['Gloss', 'gloss', 'like', '%1%'],
                ['not', ['Form', 'morphemeBreak', 'regex', '[18][5-7]']],
                ['or', [
                    ['Form', 'datetimeModified', '=', todayTimestamp.isoformat()],
                    ['Form', 'dateElicited', '=', jan1.isoformat()]]]]]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        # Emulate the search Pythonically
        resultSet = [f for f in forms if
            '1' in ' '.join([g['gloss'] for g in f['glosses']]) and
            not re.search('[18][5-7]', f['morphemeBreak']) and
            (todayTimestamp.isoformat().split('.')[0] == f['datetimeModified'].split('.')[0] or
             (f['dateElicited'] and jan1.isoformat() == f['dateElicited']))]
        assert len(resp) == len(resultSet)

        # A complex search entailing multiple joins
        tagNames = ['name 2', 'name 4', 'name 88']
        patt = '([13579][02468])|([02468][13579])'
        jsonQuery = json.dumps({'query': {'filter': [
            'or', [
                ['Gloss', 'gloss', 'like', '%1%'],
                ['Tag', 'name', 'in', ['name 2', 'name 4', 'name 88']],
                ['and', [
                    ['not', ['File', 'name', 'regex', patt]],
                    ['Form', 'dateElicited', '!=', None]]]]]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        # Emulate the search in Python
        # Note that the Python-based regexp for SQLite requires that the attribute
        # being searched be Python-truthy in order for the pattern to match.  I doubt
        # that this is the behaviour of MySQL's regexp...
        resultSet = [f for f in forms if
            '1' in ' '.join([g['gloss'] for g in f['glosses']]) or
            set([t['name'] for t in f['tags']]) & set(tagNames) or
            (f['files'] and
             not re.search(patt, ', '.join([fi['name'] for fi in f['files']])) and
             f['dateElicited'] is not None)]
        assert len(resp) == len(resultSet)

        # A super complex search ...  The implicit assertion is that a 200 status
        # code is returned.  At this point I am not going to bother attempting to
        # emulate this query in Python ...
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['Form', 'transcription', 'like', '%5%'],
                ['Form', 'morphemeBreak', 'like', '%9%'],
                ['not', ['Gloss', 'gloss', 'like', '%6%']],
                ['or', [
                    ['Form', 'datetimeEntered', '<', todayTimestamp.isoformat()],
                    ['Form', 'datetimeModified', '>', yesterdayTimestamp.isoformat()],
                    ['not', ['Form', 'dateElicited', 'in', [jan1.isoformat(), jan3.isoformat()]]],
                    ['and', [
                        ['Form', 'enterer', 'regex', '[135680]'],
                        ['Form', 'id', '<', 90]
                    ]]
                ]],
                ['not', ['not', ['not', ['Tag', 'name', '=', 'name 7']]]]
            ]
        ]}})
        response = self.app.post(url('/forms/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

    #@nottest
    def test_search_y_paginator(self):
        """Tests SEARCH /forms: paginator."""
        forms = json.loads(json.dumps(h.getForms(), cls=h.JSONOLDEncoder))

        # A basic search with a paginator provided.
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'like', '%T%']},
            'paginator': {'page': 2, 'itemsPerPage': 10}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [f for f in forms if 'T' in f['transcription']]
        assert resp['paginator']['count'] == len(resultSet)
        assert len(resp['items']) == 10
        assert resp['items'][0]['id'] == resultSet[10]['id']
        assert resp['items'][-1]['id'] == resultSet[19]['id']

        # An invalid paginator (here 'page' is less than 1) will result in formencode.Invalid
        # being raised resulting in a response with a 400 status code and a JSON error msg.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['Form', 'transcription', 'like', '%T%']},
            'paginator': {'page': 0, 'itemsPerPage': 10}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

        # Some "invalid" paginators will silently fail.  For example, if there is
        # no 'pages' key, then GET /forms will just assume there is no paginator
        # and all of the results will be returned.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['Form', 'transcription', 'like', '%T%']},
            'paginator': {'pages': 0, 'itemsPerPage': 10}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len([f for f in forms if 'T' in f['transcription']])

        # Adding a 'count' key to the paginator object in the request will spare
        # the server from running query.count().  Note that the server will not
        # attempt to verify the count (since that would defeat the purpose) but
        # will simply pass it back.  The server trusts that the client is passing
        # in a factual count.  Here we pass in an inaccurate count for demonstration.
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'like', '%T%']},
            'paginator': {'page': 2, 'itemsPerPage': 16, 'count': 750}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['paginator']['count'] == 750
        assert len(resp['items']) == 16
        assert resp['items'][0]['id'] == resultSet[16]['id']
        assert resp['items'][-1]['id'] == resultSet[31]['id']

    #@nottest
    def test_search_z_order_by(self):
        """Tests POST /forms/search: order by."""
        forms = json.loads(json.dumps(h.getForms(), cls=h.JSONOLDEncoder))

        # order by transcription ascending
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Form', 'transcription', 'asc']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[-1]['transcription'] == u'TRANSCRIPTION 99'
        assert resp[0]['transcription'] == u'transcription 1'

        # order by transcription descending
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Form', 'transcription', 'desc']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[-1]['transcription'] == u'transcription 1'
        assert resp[0]['transcription'] == u'TRANSCRIPTION 99'

        # order by gloss ascending
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Gloss', 'gloss', 'asc']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['glosses'] == [] # Form # 87 has no glosses
        assert resp[1]['glosses'][0]['gloss'] == u'gloss 1'
        assert resp[-1]['glosses'][0]['gloss'] == u'gloss 99'

        # order by with missing direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Gloss', 'gloss']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['glosses'] == [] # Form # 87 has no glosses
        assert resp[1]['glosses'][0]['gloss'] == u'gloss 1'
        assert resp[-1]['glosses'][0]['gloss'] == u'gloss 99'

        # order by with unknown direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Gloss', 'gloss', 'descending']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['glosses'] == [] # Form # 87 has no glosses
        assert resp[1]['glosses'][0]['gloss'] == u'gloss 1'
        assert resp[-1]['glosses'][0]['gloss'] == u'gloss 99'

        # syntactically malformed order by
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Gloss']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        # searches with lexically malformed order bys
        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Form', 'foo', 'desc']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.foo'] == u'Searching on Form.foo is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

        jsonQuery = json.dumps({'query': {
                'filter': ['Form', 'transcription', 'regex', '[tT]'],
                'orderBy': ['Foo', 'id', 'desc']}})
        response = self.app.post(url('/forms/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Foo'] == u'Searching the Form model by joining on the Foo model is not possible'
        assert resp['errors']['Foo.id'] == u'Searching on Foo.id is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'

    #@nottest
    def test_search_za_restricted(self):
        """Tests SEARCH /forms: restricted forms."""

        # First restrict the even-numbered forms
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        forms = h.getForms()
        formCount = len(forms)
        for form in forms:
            if int(form.transcription.split(' ')[-1]) % 2 == 0:
                form.tags.append(restrictedTag)
        Session.commit()
        restrictedForms = Session.query(model.Form).filter(
            model.Tag.name==u'restricted').outerjoin(model.Form.tags).all()
        restrictedFormCount = len(restrictedForms)

        # A viewer will only be able to see the unrestricted forms
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'regex', '[tT]']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_viewer)
        resp = json.loads(response.body)
        assert len(resp) == restrictedFormCount
        assert 'restricted' not in [
            x['name'] for x in reduce(list.__add__, [f['tags'] for f in resp])]

        # An administrator will be able to access all forms
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'regex', '[tT]']}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == formCount
        assert 'restricted' in [
            x['name'] for x in reduce(list.__add__, [f['tags'] for f in resp])]

        # Filter out restricted forms and do pagination
        jsonQuery = json.dumps({'query': {'filter':
            ['Form', 'transcription', 'regex', '[tT]']},
            'paginator': {'page': 3, 'itemsPerPage': 7}})
        response = self.app.request(url('forms'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_viewer)
        resp = json.loads(response.body)
        resultSet = [f for f in forms
                        if int(f.transcription.split(' ')[-1]) % 2 != 0]
        assert resp['paginator']['count'] == restrictedFormCount
        assert len(resp['items']) == 7
        assert resp['items'][0]['id'] == resultSet[14].id

    #@nottest
    def test_z_cleanup(self):
        """Tests POST /forms/search: clean up the database."""

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
        response = self.app.get(url('forms'), extra_environ=extra_environ)