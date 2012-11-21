import re
from old.tests import *
from nose.tools import nottest
import simplejson as json
import logging
from datetime import date, datetime, timedelta
import old.model as model
import old.model.meta as meta
import old.lib.helpers as h

# TODO: test like and regexp with capitalization -- does one ignore it?  is this db-specific?
#     regexp is case-sensitive (makes sense since it's Pythonic for SQLite)
#     like is case-insensitive (something to do with collation ...)
# TODO: test regex patterns of varying complexity
# TODO: test searches on one/many-to-many relations: does only one object need to match the search expression?

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
    meta.Session.commit()

def addTestModelsToSession(modelName, n, attrs):
    for i in range(1, n + 1):
        m = getattr(model, modelName)()
        for attr in attrs:
            setattr(m, attr, u'%s %s' % (attr, i))
        meta.Session.add(m)

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
        meta.Session.add(f)
    meta.Session.commit()

def createTestData(n=100):
    createTestModels(n)
    createTestForms(n)


class TestFormsearchesController(TestController):

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}
    n = 100

    # Clear all models in the database except Language; recreate the users.
    def tearDown(self):
        """
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        meta.Session.add_all([administrator, contributor, viewer])
        meta.Session.commit()

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        response = self.app.get(url('forms'), extra_environ=extra_environ)
        """

    @nottest
    def test_index(self):
        response = self.app.get(url('formsearches'))
        #log.debug(json.loads(response.body))
        # Test response...

    # There are 24 distinct tests (a-x) of the create action.  Aside from the
    # requirement that the initialize "test" needs to run first, these create
    # tests do not need to be executed in the order determined by their names;
    # it just helps in locating them.
    #@nottest
    def test_0_create_a_initialize(self):
        """Tests POST /formsearches: initialize database."""
        # Add a bunch of data to the db.
        createTestData(self.n)

    @nottest
    def test_a_create_b_equals(self):
        """Tests POST /formsearches: equals."""
        # Simple == search on transcriptions
        jsonQuery = json.dumps(['Form', 'transcription', '=', 'transcription 10'])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['transcription'] == u'transcription 10'

    @nottest
    def test_a_create_c_not_equals(self):
        """Tests POST /formsearches: not equals."""
        jsonQuery = json.dumps(['not', ['Form', 'transcription', '=', u'transcription 10']])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == self.n - 1
        assert u'transcription 10' not in [f['transcription'] for f in resp]

    #@nottest
    def test_a_create_d_like(self):
        """Tests POST /formsearches: like."""
        jsonQuery = json.dumps(['Form', 'transcription', 'like', u'%1%'])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20  # 1, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 31, 41, 51, 61, 71, 81, 91, 100

        # Case-sensitive like.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(['Form', 'transcription', 'like', u'%T%'])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

    @nottest
    def test_a_create_e_not_like(self):
        """Tests POST /formsearches: not like."""
        jsonQuery = json.dumps(['not', ['Form', 'transcription', 'like', u'%1%']])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 80

    #@nottest
    def test_a_create_f_regexp(self):
        """Tests POST /formsearches: regular expression."""
        jsonQuery = json.dumps(['Form', 'transcription', 'regex', u'[345]2'])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert sorted([f['transcription'] for f in resp]) == \
            [u'TRANSCRIPTION 52', u'transcription 32', u'transcription 42']
        assert len(resp) == 3  # 32, 42, 52

        # Case-sensitive regexp.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(['Form', 'transcription', 'regex', u'T'])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        # Case-sensitive regexp.  This shows that _collateAttribute is working
        # as expected in SQLAQueryBuilder.
        jsonQuery = json.dumps(['Form', 'transcription', 'regex', u'T'])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

    @nottest
    def test_a_create_g_not_regexp(self):
        """Tests POST /formsearches: not regular expression."""
        jsonQuery = json.dumps(['not', ['Form', 'transcription', 'regexp', u'[345]2']])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 97

    @nottest
    def test_a_create_h_empty(self):
        """Tests POST /formsearches: is NULL."""
        jsonQuery = json.dumps(['Form', 'narrowPhoneticTranscription', '=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # Same as above but with a double negative
        jsonQuery = json.dumps(['not', ['Form', 'narrowPhoneticTranscription', '!=', None]])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

    @nottest
    def test_a_create_i_not_empty(self):
        """Tests POST /formsearches: is not NULL."""
        jsonQuery = json.dumps(['not', ['Form', 'narrowPhoneticTranscription', '=', None]])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

        # Same as above, but with !=, i.e., __ne__
        jsonQuery = json.dumps(['Form', 'narrowPhoneticTranscription', '!=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

    @nottest
    def test_a_create_j_invalid_json(self):
        """Tests POST /formsearches: invalid JSON params."""
        jsonQuery = json.dumps(['not', ['Form', 'narrowPhoneticTranscription', '=', None]])
        jsonQuery = jsonQuery[:-1]  # Cut off the end to make it bad!
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'JSON decode error: the parameters provided were not valid JSON.'

    @nottest
    def test_a_create_k_malformed_query(self):
        """Tests POST /formsearches: malformed query."""

        # TypeError - bad num args: 'NOT' will be treated as the first arg to
        # _getSimpleFilterExpression and ['Form', 'transcription', '=', 10] will be passed
        # as the second -- two more are required.
        jsonQuery = json.dumps(['NOT', ['Form', 'id', '=', 10]])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # After recognizing 'not', the query builder will look at only the next
        # list and ignore all the rest.
        jsonQuery = json.dumps(['not', ['Form', 'transcription', '=', 'transcription 10'], 
            ['Form', 'transcription', '=', 'transcription 10'], ['Form', 'transcription', '=', 'transcription 10']])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99
        assert 'transcription 10' not in [f['transcription'] for f in resp]

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps(['not'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[0] is called.
        jsonQuery = json.dumps([])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # IndexError will be raised when python[1] is called.
        jsonQuery = json.dumps(['and'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['IndexError'] == u'list index out of range'

        # TypeError bad num args will be triggered when _getSimpleFilterExpression is
        # called on a string whose len is not 4, i.e., 'id' or '='.
        jsonQuery = json.dumps(['and', ['Form', 'id', '=', '1099']])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'TypeError' in resp['errors']
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

        # TypeError when asking whether [] is in a dict (lists are unhashable)
        jsonQuery = json.dumps([[], 'a', 'a', 'a'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['TypeError'] == u"unhashable type: 'list'"
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'

    @nottest
    def test_a_create_l_lexical_semantic_error(self):
        """Tests POST /formsearches: lexical & semantic errors.
        
        These are when SQLAQueryBuilder.py raises a OLDSearchParseError because a
        relation is not permitted, e.g., 'contains', or not permitted for a
        given attribute.
        """

        # searchParser.py does not allow the contains relation (OLDSearchParseError)
        jsonQuery = json.dumps(['Form', 'transcription', 'contains', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert 'Form.transcription.contains' in resp['errors']

        # model.Form.glosses.__eq__('abcdefg') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps(['Form', 'glosses', '=', u'abcdefg'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

        # model.Form.tags.regexp('xyz') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps(['Form', 'tags', 'regex', u'xyz'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Malformed OLD query error'] == u'The submitted query was malformed'
        assert resp['errors']['Form.tags.regex'] == u'The relation regex is not permitted for Form.tags'

        # model.Form.glosses.like('gloss') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps(['Form', 'glosses', 'like', u'abc'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.glosses.like'] == u'The relation like is not permitted for Form.glosses'

        # model.Form.tags.__eq__('tag') will raise a custom OLDSearchParseError
        jsonQuery = json.dumps(['Form', 'tags', '__eq__', u'tag'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'InvalidRequestError' in resp['errors']

    @nottest
    def test_a_create_m_conjunction(self):
        """Tests POST /formsearches: conjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]
        models = getTestModels()

        # 1 conjunct -- pointless, but it works...
        query = [
            'and', [
                ['Form', 'transcription', 'like', u'%2%']
            ]
        ]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 19

        # 2 conjuncts
        query = [
            'and', [
                ['Form', 'transcription', 'like', u'%2%'],
                ['Form', 'transcription', 'like', u'%1%']
            ]
        ]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert sorted([f['transcription'] for f in resp]) == ['transcription 12', 'transcription 21']

        # More than 2 conjuncts
        query = [
            'and', [
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'elicitor', '=', contributor.id],
                ['Form', 'elicitationMethod', '=', models['elicitationMethods'][49].id]
            ]
        ]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 3
        assert sorted([f['transcription'] for f in resp]) == ['TRANSCRIPTION 51', 'TRANSCRIPTION 61', 'TRANSCRIPTION 71']

        # Multiple redundant conjuncts -- proof of possibility
        query = [
            'and', [
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
                ['Form', 'transcription', 'like', u'%1%'],
            ]
        ]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20

    @nottest
    def test_a_create_n_disjunction(self):
        """Tests POST /formsearches: disjunction."""
        users = h.getUsers()
        contributor = [u for u in users if u.role == u'contributor'][0]

        # 1 disjunct -- pointless, but it works...
        query = [
            'or', [
                ['Form', 'transcription', 'like', u'%2%']   # 19 total
            ]
        ]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 19

        # 2 disjuncts
        query = [
            'or', [
                ['Form', 'transcription', 'like', u'%2%'],    # 19; Total: 19
                ['Form', 'transcription', 'like', u'%1%']     # 18 (20 but '12' and '21' shared with '2'); Total: 37
            ]
        ]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 37

        # 3 disjuncts
        query = [
            'or', [
                ['Form', 'transcription', 'like', u'%2%'],    # 19; Total: 19
                ['Form', 'transcription', 'like', u'%1%'],    # 18 (20 but '12' and '21' shared with '2'); Total: 37
                ['Form', 'elicitor', '=', contributor.id]   # 39 (50 but 11 shared with '2' and '1'); Total: 76
            ]
        ]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 76

    @nottest
    def test_a_create_o_int(self):
        """Tests POST /formsearches: integer searches."""

        forms = h.getForms()
        formIds = [f.id for f in forms]

        # = int
        jsonQuery = json.dumps(['Form', 'id', '=', formIds[1]])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1
        assert resp[0]['id'] == formIds[1]

        # < int (str)
        jsonQuery = json.dumps(['Form', 'id', '<', str(formIds[16])]) # Thanks to SQLAlchemy, a string will work here too
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 16

        # >= int
        jsonQuery = json.dumps(['Form', 'id', '>=', formIds[97]])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 3

        # in array
        jsonQuery = json.dumps(['Form', 'id', 'in', [formIds[12], formIds[36], formIds[28], formIds[94]]])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4
        assert sorted([f['id'] for f in resp]) == [formIds[12], formIds[28], formIds[36], formIds[94]]

        # in None -- Error
        jsonQuery = json.dumps(['Form', 'id', 'in', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.id.in_'] == u"Invalid filter expression: Form.id.in_(None)"

        # in int -- Error
        jsonQuery = json.dumps(['Form', 'id', 'in', 2])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.id.in_'] == u"Invalid filter expression: Form.id.in_(2)"

        # regex int - The OLD's Python-based regexp implementation for SQLite will
        # automatically convert a non-string field value to a string before doing
        # the regexp comparison.  I believe that this parallels MySQL's regexp
        # behaviour accurately.
        strPatt = u'[13][58]'
        patt = re.compile(strPatt)
        expectedIdMatches = [f.id for f in forms if patt.search(str(f.id))]        
        jsonQuery = json.dumps(['Form', 'id', 'regex', u'[13][58]'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedIdMatches)
        assert sorted([f['id'] for f in resp]) == sorted(expectedIdMatches)

        # like int - RDBMS treats ints as strings for LIKE search
        jsonQuery = json.dumps(['Form', 'id', 'like', u'%2%'])
        expectedMatches = [i for i in formIds if u'2' in str(i)]
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedMatches)

    @nottest
    def test_a_create_p_date(self):
        """Tests POST /formsearches: date searches."""

        # = date
        jsonQuery = json.dumps(['Form', 'dateElicited', '=', jan1.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25
        jsonQuery = json.dumps(['Form', 'dateElicited', '=', jan4.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 23

        # != date -- *NOTE:* the NULL dateElicited values will not be counted.
        # The implicit query is 'is not null and != 2012-01-01'
        jsonQuery = json.dumps(['Form', 'dateElicited', '!=', jan1.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 73
        jsonQuery = json.dumps(['Form', 'dateElicited', '!=', jan4.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # To get what one really wants (perhaps), test for NULL too:
        query = ['or', [['Form', 'dateElicited', '!=', jan1.isoformat()],
                ['Form', 'dateElicited', '=', None]]]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # < date
        jsonQuery = json.dumps(['Form', 'dateElicited', '<', jan1.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0
        jsonQuery = json.dumps(['Form', 'dateElicited', '<', jan3.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        # <= date
        jsonQuery = json.dumps(['Form', 'dateElicited', '<=', jan3.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        # > date
        jsonQuery = json.dumps(['Form', 'dateElicited', '>', jan2.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 48
        jsonQuery = json.dumps(['Form', 'dateElicited', '>', '0001-01-01'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 98

        # >= date
        jsonQuery = json.dumps(['Form', 'dateElicited', '>=', jan2.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 73

        # =/!= None
        jsonQuery = json.dumps(['Form', 'dateElicited', '=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

        jsonQuery = json.dumps(['Form', 'dateElicited', '__ne__', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 98

    @nottest
    def test_a_create_q_date_invalid(self):
        """Tests POST /formsearches: invalid date searches."""

        # = invalid date
        jsonQuery = json.dumps(['Form', 'dateElicited', '=', '12-01-01'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 12-01-01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        jsonQuery = json.dumps(['Form', 'dateElicited', '=', '2012-01-32'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 2012-01-32'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on invalid date will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(['Form', 'dateElicited', 'regex', '01'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['date 01'] == \
            u'Date search parameters must be valid ISO 8601 date strings.'

        # regex on valid date will work and will act just like = -- no point
        jsonQuery = json.dumps(['Form', 'dateElicited', 'regex', '2012-01-01'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps(['Form', 'dateElicited', 'like', '2012-01-01'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 25

        # in_ on a date.  This will raise a TypeError ('datetime.date' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps(['Form', 'dateElicited', 'in', '2012-01-02'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.dateElicited.in_'] == u'Invalid filter expression: Form.dateElicited.in_(datetime.date(2012, 1, 2))'

        # in_ on a list of dates works (SQLAQueryBuilder generates a list of date objects)
        jsonQuery = json.dumps(['Form', 'dateElicited', 'in', ['2012-01-01', '2012-01-02']])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

    @nottest
    def test_a_create_r_datetime(self):
        """Tests POST /formsearches: datetime searches."""

        # = datetime
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '=', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '=', yesterdayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        # != datetime -- *NOTE:* the NULL datetimeEntered values will not be counted.
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '!=', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '!=', yesterdayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # To get what one really wants (perhaps), test for NULL too:
        query = ['or', [['Form', 'datetimeEntered', '!=', todayTimestamp.isoformat()],
                ['Form', 'datetimeEntered', '=', None]]]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 51

        # < datetime
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '<', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 50

        # <= datetime
        jsonQuery = json.dumps(['Form', 'datetimeModified', '<=', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # > datetime
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '>', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0
        # Note: Python2.6/Debian(?) bug: using a year before 1900 will cause problems: 
        # ValueError: year=1 is before 1900; the datetime strftime() methods require year >= 1900
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '>', '1901-01-01T09:08:07'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # >= datetime
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '>=', yesterdayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # =/!= None
        jsonQuery = json.dumps(['Form', 'datetimeEntered', '=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        jsonQuery = json.dumps(['Form', 'datetimeEntered', '__ne__', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # datetime in today
        midnightToday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        midnightTomorrow = midnightToday + dayDelta
        query = ['and', [['Form', 'datetimeEntered', '>', midnightToday.isoformat()],
                         ['Form', 'datetimeEntered', '<', midnightTomorrow.isoformat()]]]
        jsonQuery = json.dumps(query)
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

    @nottest
    def test_a_create_s_datetime_invalid(self):
        """Tests POST /formsearches: invalid datetime searches."""

        # = invalid datetime
        jsonQuery = json.dumps(['Form', 'datetimeModified', '=', '12-01-01T09'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 12-01-01T09'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        jsonQuery = json.dumps(['Form', 'datetimeModified', '=', '2012-01-30T09:08:61'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 2012-01-30T09:08:61'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # Trailing period and too many microseconds will both succeed.
        jsonQuery = json.dumps(['Form', 'datetimeModified', '=', '2012-01-30T09:08:59.123456789123456789123456789'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        jsonQuery = json.dumps(['Form', 'datetimeModified', '=', '2012-01-30T09:08:59.'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)

        # regex on invalid datetime will fail because SQLA only allows Python datetime
        # objects as input on queries (though None is also allowed to test for nullness)
        jsonQuery = json.dumps(['Form', 'datetimeModified', 'regex', '01'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['datetime 01'] == \
            u'Datetime search parameters must be valid ISO 8601 datetime strings.'

        # regex on valid datetime will work and will act just like = -- no point
        jsonQuery = json.dumps(['Form', 'datetimeModified', 'regex', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # Same thing for like, it works like = but what's the point?
        jsonQuery = json.dumps(['Form', 'datetimeModified', 'like', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # in_ on a datetime.  This will raise a TypeError ('datetime.datetime' object is
        # not iterable) that is caught in _getFilterExpression
        jsonQuery = json.dumps(['Form', 'datetimeModified', 'in', todayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.datetimeModified.in_'] == \
            u'Invalid filter expression: Form.datetimeModified.in_(%s)' % repr(todayTimestamp)

        # in_ on a list of datetimes works (SQLAQueryBuilder generates a list of datetime objects)
        jsonQuery = json.dumps(['Form', 'datetimeModified', 'in', [todayTimestamp.isoformat(), yesterdayTimestamp.isoformat()]])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

    @nottest
    def test_a_create_t_many_to_one(self):
        """Tests POST /formsearches: searches on many-to-one attributes."""

        testModels = getTestModels()
        users = h.getUsers()
        forms = h.getForms()
        viewer = [u for u in users if u.role == u'viewer'][0]
        contributor = [u for u in users if u.role == u'contributor'][0]
        administrator = [u for u in users if u.role == u'administrator'][0]

        # = int
        jsonQuery = json.dumps(['Form', 'enterer', '=', contributor.id])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100

        jsonQuery = json.dumps(['Form', 'speaker', '=', testModels['speakers'][0].id])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 49

        # in array of ints
        jsonQuery = json.dumps(['Form', 'speaker', 'in', [s.id for s in testModels['speakers']]])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # <
        jsonQuery = json.dumps(['Form', 'elicitationMethod', '<', 56])
        expectedForms = [f for f in forms if f.elicitationmethod_id < 56]
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

        # regex
        jsonQuery = json.dumps(['Form', 'elicitationMethod', 'regex', '5'])
        expectedForms = [f for f in forms if '5' in str(f.elicitationmethod_id)]
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

        jsonQuery = json.dumps(['Form', 'elicitationMethod', 'regex', '[56]'])
        expectedForms = [f for f in forms 
            if '5' in str(f.elicitationmethod_id) or '6' in str(f.elicitationmethod_id)] 
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

        # like
        jsonQuery = json.dumps(['Form', 'syntacticCategory', 'like', '%5%'])
        expectedForms = [f for f in forms if '5' in str(f.syntacticcategory_id)]
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(expectedForms)

    @nottest
    def test_a_create_u_one_to_many(self):
        """Tests POST /formsearches: searches on one-to-many attributes, viz. Gloss."""

        # gloss.gloss =
        jsonQuery = json.dumps(['Gloss', 'gloss', '=', 'gloss 1'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # gloss.glossGrammaticality
        jsonQuery = json.dumps(['Gloss', 'glossGrammaticality', '=', '*'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 24

        # gloss.gloss like
        jsonQuery = json.dumps(['Gloss', 'gloss', 'like', '%1%'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20

        # gloss.gloss regexp
        jsonQuery = json.dumps(['Gloss', 'gloss', 'regex', '[13][25]'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4

        # gloss.gloss in_
        jsonQuery = json.dumps(['Gloss', 'gloss', 'in_', [u'gloss 1', u'gloss 2']])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # gloss.gloss <
        jsonQuery = json.dumps(['Gloss', 'gloss', '<', u'z'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # gloss.datetimeModified
        jsonQuery = json.dumps(['Gloss', 'datetimeModified', '>', yesterdayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # To search for the presence/absence of glosses, one must use the
        # glosses attribute of the Form model.
        jsonQuery = json.dumps(['Form', 'glosses', '=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        jsonQuery = json.dumps(['Form', 'glosses', '!=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 99

        # Using anything other than =/!= on Form.glosses will raise an error.
        jsonQuery = json.dumps(['Form', 'glosses', 'like', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.glosses.like'] == u'The relation like is not permitted for Form.glosses'

        # Using a value other than None on Form.glosses will also raise an error
        jsonQuery = json.dumps(['Form', 'glosses', '=', 'gloss 1'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

    @nottest
    def test_a_create_v_many_to_many(self):
        """Tests POST /formsearches: searches on many-to-many attributes, i.e., Tag, File, Collection."""

        # tag.name =
        jsonQuery = json.dumps(['Tag', 'name', '=', 'name 76'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # file.name like
        jsonQuery = json.dumps(['File', 'name', 'like', '%name 6%'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 4

        # file.name regexp
        jsonQuery = json.dumps(['File', 'name', 'regex', 'name [67]'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 14

        # tag.name in_
        jsonQuery = json.dumps(['Tag', 'name', 'in_', [u'name 77', u'name 79', u'name 99']])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 3

        # tag.name <
        jsonQuery = json.dumps(['Tag', 'name', '<', u'name 8'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 5   # 76, 77, 78, 79, 100

        # file.datetimeModified
        jsonQuery = json.dumps(['File', 'datetimeModified', '>', yesterdayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20  # All forms with a file attached

        jsonQuery = json.dumps(['File', 'datetimeModified', '<', yesterdayTimestamp.isoformat()])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0

        # To search for the presence/absence of tags/files/collections, one must use the
        # tags/files/collections attributes of the Form model.
        jsonQuery = json.dumps(['Form', 'tags', '=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 75

        jsonQuery = json.dumps(['Form', 'files', '!=', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 20

        # Using anything other than =/!= on Form.tags/files/collections will raise an error.
        jsonQuery = json.dumps(['Form', 'tags', 'like', None])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Form.tags.like'] == u'The relation like is not permitted for Form.tags'

        jsonQuery = json.dumps(['Form', 'files', '=', 'file 80'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['InvalidRequestError'] == \
            u"Can't compare a collection to an object or collection; use contains() to test for membership."

    @nottest
    def test_a_create_w_in(self):
        """Tests POST /formsearches: searches using the in_ relation."""

        # Array value -- all good.
        jsonQuery = json.dumps(['Form', 'transcription', 'in', ['transcription 1']])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # String value -- no error because strings are iterable; but no results
        jsonQuery = json.dumps(['Form', 'transcription', 'in', 'transcription 1'])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 0

    @nottest
    def test_a_create_x_complex(self):
        """Tests POST /formsearches: complex searches."""
        forms = json.loads(json.dumps(h.getForms(), cls=h.JSONOLDEncoder))

        # A fairly complex search
        jsonQuery = json.dumps([
            'and', [
                ['Gloss', 'gloss', 'like', '%1%'],
                ['not', ['Form', 'morphemeBreak', 'regex', '[18][5-7]']],
                ['or', [
                    ['Form', 'datetimeModified', '=', todayTimestamp.isoformat()],
                    ['Form', 'dateElicited', '=', jan1.isoformat()]]]]])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        # Emulate the search Pythonically
        #log.debug(str([[g['gloss'] for g in f['glosses']] for f in forms]))
        #log.debug(str([[g for g in f['glosses']] for f in forms]))
        resultSet = [f for f in forms if
            '1' in ' '.join([g['gloss'] for g in f['glosses']]) and
            not re.search('[18][5-7]', f['morphemeBreak']) and
            (todayTimestamp.isoformat().split('.')[0] == f['datetimeModified'].split('.')[0] or
             (f['dateElicited'] and jan1.isoformat() == f['dateElicited']))]
        assert len(resp) == len(resultSet)

        # A complex search entailing multiple joins
        tagNames = ['name 2', 'name 4', 'name 88']
        patt = '([13579][02468])|([02468][13579])'
        jsonQuery = json.dumps([
            'or', [
                ['Gloss', 'gloss', 'like', '%1%'],
                ['Tag', 'name', 'in', ['name 2', 'name 4', 'name 88']],
                ['and', [
                    ['not', ['File', 'name', 'regex', patt]],
                    ['Form', 'dateElicited', '!=', None]]]]])
        response = self.app.post(url('formsearches'), jsonQuery,
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
        jsonQuery = json.dumps([
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
        ])
        response = self.app.post(url('formsearches'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

    @nottest
    def test_a_create_y_cleanup(self):
        """Tests POST /formsearches: clean up the database."""

        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        meta.Session.add_all([administrator, contributor, viewer])
        meta.Session.commit()

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        response = self.app.get(url('forms'), extra_environ=extra_environ)

    @nottest
    def test_new(self):
        response = self.app.get(url('new_formsearch'))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('formsearch', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('formsearch', id=1))
