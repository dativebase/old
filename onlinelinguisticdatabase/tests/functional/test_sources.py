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
from onlinelinguisticdatabase.model import Source
from onlinelinguisticdatabase.lib.bibtex import entryTypes
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder

log = logging.getLogger(__name__)



################################################################################
# Functions for creating & retrieving test data
################################################################################

todayTimestamp = datetime.datetime.now()
dayDelta = datetime.timedelta(1)
yesterdayTimestamp = todayTimestamp - dayDelta

def createTestModels(n=100):
    addTestModelsToSession('File', n, ['name'])
    Session.commit()

def addTestModelsToSession(modelName, n, attrs):
    for i in range(1, n + 1):
        m = getattr(model, modelName)()
        for attr in attrs:
            setattr(m, attr, u'%s %s' % (attr, i))
        Session.add(m)

def getTestModels():
    return {'files': h.getFiles()}

def createTestSources(n=100):
    """Create n sources with various properties.  A testing ground for searches!
    """
    files = getTestModels()['files']
    users = h.getUsers()
    viewer = [u for u in users if u.role == u'viewer'][0]
    contributor = [u for u in users if u.role == u'contributor'][0]
    administrator = [u for u in users if u.role == u'administrator'][0]

    for i in range(1, n + 1):
        s = model.Source()
        s.key = unicode(i)
        if i in range(1, 11):
            s.type = u'article'
            s.author = u'Author Mc%d' % i
            s.title = u'Title %d' % i
            s.journal = u'Journal %d' % i
            s.year = int('199%s' % str(i)[-1])
        elif i in range(11, 21):
            s.type = u'book'
            s.author = u'Author Mc%d' % i
            s.title = u'Title %d' % i
            s.journal = u'Publisher %d' % i
            s.year = int('199%s' % str(i)[-1])
        elif i in range(21, 31):
            s.type = u'booklet'
            s.title = u'Title %d' % i
        elif i in range(31, 41):
            s.type = u'conference'
            s.author = u'Author Mc%d' % i
            s.title = u'Title %d' % i
            s.booktitle = u'Book Title %d' % i
            s.year = int('199%s' % str(i)[-1])
        elif i in range(41, 51):
            s.type = u'inbook'
            s.editor = u'Editor Mc%d' % i
            s.title = u'Title %d' % i
            s.chapter = unicode(i)
            s.pages = u'9--36'
            s.publisher = u'Publisher %d' % i
            s.year = int('199%s' % str(i)[-1])
        elif i in range(51, 61):
            s.type = u'incollection'
            s.author = u'Author Mc%d' % i
            s.title = u'Title %d' % i
            s.booktitle = u'Book Title %d' % i
            s.publisher = u'Publisher %d' % i
            s.year = int('199%s' % str(i)[-1])
        elif i in range(61, 71):
            s.type = u'inproceedings'
            s.author = u'Author Mc%d' % i
            s.title = u'Title %d' % i
            s.booktitle = u'Book Title %d' % i
            s.year = int('199%s' % str(i)[-1])
        elif i in range(71, 81):
            s.type = u'manual'
            s.title = u'Title %d' % i
        elif i in range(81, 91):
            s.type = u'mastersthesis'
            s.author = u'Author Mc%d' % i
            s.title = u'Title %d' % i
            s.school = u'The University of %d' % i
            s.year = int('199%s' % str(i)[-1])
        else:
            s.type = u'misc'

        if i % 2 == 0:
            s.file_id = files[i - 1].id

        if i > 8:
            s.datetimeModified = yesterdayTimestamp

        Session.add(s)
    Session.commit()


def createTestData(n=100):
    createTestModels(n)
    createTestSources(n)


def addSEARCHToWebTestValidMethods():
    new_valid_methods = list(webtest.lint.valid_methods)
    new_valid_methods.append('SEARCH')
    new_valid_methods = tuple(new_valid_methods)
    webtest.lint.valid_methods = new_valid_methods


class TestSourcesController(TestController):

    createParams = {
        'file': u'',
        'type': u'',
        'key': u'',
        'address': u'',
        'annote': u'',
        'author': u'',
        'booktitle': u'',
        'chapter': u'',
        'crossref': u'',
        'edition': u'',
        'editor': u'',
        'howpublished': u'',
        'institution': u'',
        'journal': u'',
        'keyField': u'',
        'month': u'',
        'note': u'',
        'number': u'',
        'organization': u'',
        'pages': u'',
        'publisher': u'',
        'school': u'',
        'series': u'',
        'title': u'',
        'typeField': u'',
        'url': u'',
        'volume': u'',
        'year': u'',
        'affiliation': u'',
        'abstract': u'',
        'contents': u'',
        'copyright': u'',
        'ISBN': u'',
        'ISSN': u'',
        'keywords': u'',
        'language': u'',
        'location': u'',
        'LCCN': u'',
        'mrnumber': u'',
        'price': u'',
        'size': u'',
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
        """Tests that GET /sources returns an array of all sources and that orderBy and pagination parameters work correctly."""

        # Add 100 sources.
        def createSourceFromIndex(index):
            source = model.Source()
            source.type = u'book'
            source.key = u'key%d' % index
            source.author = u'Chomsky, N.'
            source.title = u'Syntactic Structures %d' % index
            source.publisher = u'Mouton'
            source.year = 1957
            return source
        sources = [createSourceFromIndex(i) for i in range(1, 101)]
        Session.add_all(sources)
        Session.commit()
        sources = h.getSources(True)
        sourcesCount = len(sources)

        # Test that GET /sources gives us all of the sources.
        extra_environ = self.extra_environ_view
        response = self.app.get(url('sources'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == sourcesCount
        assert resp[0]['title'] == u'Syntactic Structures 1'
        assert resp[0]['id'] == sources[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('sources'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['title'] == sources[46].title
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Source', 'orderByAttribute': 'title',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('sources'), orderByParams,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        resultSet = sorted([s.title for s in sources], reverse=True)
        assert resultSet == [s['title'] for s in resp]
        assert response.content_type == 'application/json'

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Source', 'orderByAttribute': 'title',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('sources'), params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['title']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Source', 'orderByAttribute': 'title',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('sources'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Sourceful', 'orderByAttribute': 'titular',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('sources'), orderByParams,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp[0]['id'] == sources[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('sources'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('sources'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /sources creates a new source or returns an appropriate error
        if the input is invalid.
        """

        ########################################################################
        # BOOK
        ########################################################################

        # Attempt to create a source that has an invalid BibTeX entry type and
        # expect to fail.  Also, check that the length restrictions on the other
        # fields are working too.
        params = self.createParams.copy()
        params.update({
            'type': u'novella',
            'author': u'author' * 255
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['type'] == u'novella is not a valid BibTeX entry type'
        assert resp['errors']['author'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

        # Create a book; required: author or editor, title, publisher and year
        params = self.createParams.copy()
        params.update({
            'type': u'bOOk',    # case is irrelevant for entry types
            'key': u'chomsky57',
            'author': u'Noam Chomsky',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957,
            'edition': u'second',   # good optional attribute for a book
            'school': u'Stanford'   # doesn't make sense for a book, but it will still be saved
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourcesCount = Session.query(Source).count()
        assert resp['type'] == u'book'      # the OLD converts type to lowercase
        assert resp['school'] == u'Stanford'
        assert resp['edition'] == u'second'
        assert resp['booktitle'] == u''
        assert resp['author'] == u'Noam Chomsky'
        assert response.content_type == 'application/json'

        # Attempt to create another book with the same key and expect to fail.
        params = self.createParams.copy()
        params.update({
            'type': u'bOOk',
            'key': u'chomsky57',    # This duplicate is the bad part.
            'author': u'Fred Smith',
            'title': u'Structures Syntax-wise',
            'publisher': u'Backwoods Publishing',
            'year': 1984
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        newSourcesCount = Session.query(Source).count()
        assert sourcesCount == newSourcesCount
        assert resp['errors']['key'] == u'The submitted source key is not unique'
        assert response.content_type == 'application/json'

        # Attempt to create another book with an invalid key and expect to fail.
        params = self.createParams.copy()
        params.update({
            'type': u'bOOk',
            'key': u'cho\u0301msky57',    # Unicode characters are not permitted, PERHAPS THEY SHOULD BE? ...
            'author': u'Fred Smith',
            'title': u'Structures Syntax-wise',
            'publisher': u'Backwoods Publishing',
            'year': 1984
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        newSourcesCount = Session.query(Source).count()
        assert sourcesCount == newSourcesCount
        assert resp['errors']['key'] == u'Source keys can only contain letters, numerals and symbols (except the comma)'

        # Attempt to create a book source that is invalid because it lacks a year.
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57a',
            'author': u'Noam Chomsky',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'edition': u'second'   # good optional attribute for a book
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert resp['errors'] == \
            u'Sources of type book require values for title, publisher and year as well as a value for at least one of author and editor.'
        assert sourcesCount == newSourcesCount
        assert response.content_type == 'application/json'

        # Attempt to create a book source that is invalid because it lacks both
        # author and editor 
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57a',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert resp['errors'] == \
            u'Sources of type book require values for title, publisher and year as well as a value for at least one of author and editor.'
        assert sourcesCount == newSourcesCount
        assert response.content_type == 'application/json'

        ########################################################################
        # ARTICLE
        ########################################################################

        # Create an article; required: author, title, journal, year
        params = self.createParams.copy()
        params.update({
            'type': u'Article',    # case is irrelevant for entry types
            'key': u'bloomfield46',
            'author': u'Bloomfield, L.',
            'title': u'Algonquian',
            'year': 1946,
            'journal': u'Linguistic Structures of Native America',
            'pages': u'85--129'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert resp['type'] == u'article'      # the OLD converts type to lowercase
        assert resp['title'] == u'Algonquian'
        assert resp['author'] == u'Bloomfield, L.'
        assert resp['journal'] == u'Linguistic Structures of Native America'
        assert resp['pages'] == u'85--129'
        assert resp['year'] == 1946
        assert newSourcesCount == sourcesCount + 1
        assert response.content_type == 'application/json'

        # Attempt to create an article without a year and expect to fail
        params = self.createParams.copy()
        params.update({
            'type': u'Article',    # case is irrelevant for entry types
            'key': u'bloomfieldL46',
            'author': u'Bloomfield, L.',
            'title': u'Algonquian',
            'journal': u'Linguistic Structures of Native America',
            'pages': u'85--129'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sourcesCount = Session.query(Source).count()
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert sourcesCount == newSourcesCount
        assert resp['errors'] == \
            u'Sources of type article require values for author, title, journal and year.'
        assert response.content_type == 'application/json'

        ########################################################################
        # BOOKLET
        ########################################################################

        # Create a booklet; required: title
        params = self.createParams.copy()
        params.update({
            'type': u'BOOKLET',    # case is irrelevant for entry types
            'key': u'mypoetry',
            'title': u'My Poetry (unpublished)'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert resp['type'] == u'booklet'      # the OLD converts type to lowercase
        assert resp['title'] == u'My Poetry (unpublished)'
        assert newSourcesCount == sourcesCount + 1
        assert response.content_type == 'application/json'

        # Attempt to create a booklet without a title and expect to fail
        params = self.createParams.copy()
        params.update({
            'type': u'Booklet',    # case is irrelevant for entry types
            'key': u'mypoetry2',
            'author': 'Me Meson'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sourcesCount = Session.query(Source).count()
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert sourcesCount == newSourcesCount
        assert resp['errors'] == \
            u'Sources of type booklet require a value for title.'
        assert response.content_type == 'application/json'

        ########################################################################
        # INBOOK
        ########################################################################

        # Create an inbook; required: title, publisher, year and one of author
        # or editor and one of chapter or pages.
        params = self.createParams.copy()
        params.update({
            'type': u'inbook',    # case is irrelevant for entry types
            'key': u'vendler67',
            'title': u'Linguistics in Philosophy',
            'publisher': u'Cornell University Press',
            'year': 1967,
            'author': 'Vendler, Zeno',
            'chapter': u'4'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert resp['type'] == u'inbook'      # the OLD converts type to lowercase
        assert resp['title'] == u'Linguistics in Philosophy'
        assert resp['publisher'] == u'Cornell University Press'
        assert resp['year'] == 1967
        assert resp['author'] == u'Vendler, Zeno'
        assert resp['chapter'] == u'4'
        assert resp['pages'] == u''
        assert newSourcesCount == sourcesCount + 1
        assert response.content_type == 'application/json'

        # Attempt to create an inbook without a chapter or pages and expect to fail
        params = self.createParams.copy()
        params.update({
            'type': u'inbook',    # case is irrelevant for entry types
            'key': u'vendler67again',
            'title': u'Linguistics in Philosophy',
            'publisher': u'Cornell University Press',
            'year': 1967,
            'author': 'Vendler, Zeno'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sourcesCount = Session.query(Source).count()
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert sourcesCount == newSourcesCount
        assert resp['errors'] == \
            u'Sources of type inbook require values for title, publisher and year as well as a value for at least one of author and editor and at least one of chapter and pages.'
        assert response.content_type == 'application/json'

        ########################################################################
        # MISC
        ########################################################################

        # Create a misc; required: nothing.
        params = self.createParams.copy()
        params.update({
            'type': u'misc',    # case is irrelevant for entry types
            'key': u'manuel83',
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourcesCount = newSourcesCount
        newSourcesCount = Session.query(Source).count()
        assert resp['type'] == u'misc'      # the OLD converts type to lowercase
        assert newSourcesCount == sourcesCount + 1
        assert response.content_type == 'application/json'

    @nottest
    def test_new(self):
        """Tests that GET /sources/new returns the list of valid BibTeX entry types."""
        response = self.app.get(url('new_source'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['types'] == sorted(entryTypes.keys())
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /sources/1 updates an existing source."""

        # Create a book to update.
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Noam Chomsky',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourceCount = Session.query(Source).count()
        bookId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Update the book
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Chomsky, N.',   # Change the format of the author
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=bookId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newSourceCount = Session.query(Source).count()
        assert sourceCount == newSourceCount
        assert datetimeModified != originalDatetimeModified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Chomsky, N.',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=bookId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sourceCount = newSourceCount
        newSourceCount = Session.query(Source).count()
        ourBookDatetimeModified = Session.query(Source).get(bookId).datetimeModified
        assert ourBookDatetimeModified.isoformat() == datetimeModified
        assert sourceCount == newSourceCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Update by adding a file to the source
        file_ = h.generateDefaultFile()
        Session.add(file_)
        Session.commit()
        fileId = file_.id
        fileName = file_.name

        sleep(1)    # sleep for a second to ensure that MySQL can register a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Chomsky, N.',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957,
            'file': fileId
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=bookId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourceCount = newSourceCount
        newSourceCount = Session.query(Source).count()
        newDatetimeModified = resp['datetimeModified']
        assert newDatetimeModified != datetimeModified
        assert sourceCount == newSourceCount
        assert resp['file']['name'] == fileName
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /sources/id deletes the source with id=id."""

        # Create a book to delete.
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Noam Chomsky',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourceCount = Session.query(Source).count()
        bookId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Now delete the source
        response = self.app.delete(url('source', id=bookId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newSourceCount = Session.query(Source).count()
        assert newSourceCount == sourceCount - 1
        assert resp['id'] == bookId
        assert response.content_type == 'application/json'

        # Trying to get the deleted source from the db should return None
        deletedSource = Session.query(Source).get(bookId)
        assert deletedSource == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('source', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no source with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('source', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    @nottest
    def test_show(self):
        """Tests that GET /source/id returns the source with id=id or an appropriate error."""

        # Create a book to show.
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Noam Chomsky',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourceCount = Session.query(Source).count()
        bookId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Try to get a source using an invalid id
        id = 100000000000
        response = self.app.get(url('source', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no source with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('source', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('source', id=bookId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['author'] == u'Noam Chomsky'
        assert resp['year'] == 1957
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /sources/id/edit returns a JSON object of data necessary to edit the source with id=id.

        The JSON object is of the form {'source': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a book to request edit on.
        params = self.createParams.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Noam Chomsky',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sourceCount = Session.query(Source).count()
        bookId = resp['id']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_source', id=bookId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_source', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no source with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_source', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_source', id=bookId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['source']['title'] == u'Syntactic Structures'
        assert resp['data']['types'] == sorted(entryTypes.keys())
        assert response.content_type == 'application/json'

    @nottest
    def test_search(self):
        """Tests that SEARCH /sources (a.k.a. POST /sources/search) correctly returns an array of sources based on search criteria."""

        # Create some sources (and other models) to search and add SEARCH to the list of allowable methods
        createTestData(100)
        addSEARCHToWebTestValidMethods()

        sources = json.loads(json.dumps(h.getSources(True), cls=h.JSONOLDEncoder))

        # Searching where values may be NULL
        jsonQuery = json.dumps({'query': {'filter': ['Source', 'publisher', '=', None]}})
        response = self.app.post(url('/sources/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [s for s in sources if not s['publisher']]
        assert resp
        assert len(resp) == len(resultSet)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in resultSet])
        assert response.content_type == 'application/json'

        jsonQuery = json.dumps({'query': {'filter': ['Source', 'publisher', 'like', u'%P%']}})
        response = self.app.post(url('/sources/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [s for s in sources if s['publisher'] and u'P' in s['publisher']]
        assert resp
        assert len(resp) == len(resultSet)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in resultSet])
        assert response.content_type == 'application/json'

        # A fairly complex search
        jsonQuery = json.dumps({'query': {'filter': [
            'and', [
                ['Source', 'type', 'in', [u'book', u'article']],
                ['not', ['Source', 'key', 'regex', u'[537]']],
                ['or', [
                    ['Source', 'author', 'like', u'%A%'],
                    ['Source', 'year', '>', 1994]]]]]}})
        response = self.app.post(url('/sources/search'), jsonQuery,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [s for s in sources if
            s['type'] in ['book', 'article'] and
            not re.search('[537]', s['key']) and
            ('A' in s['author'] or s['year'] > 1994)]
        assert resp
        assert len(resp) == len(resultSet)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in resultSet])
        assert response.content_type == 'application/json'

        # A basic search with a paginator provided.
        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'page': 2, 'itemsPerPage': 5}})
        response = self.app.request(url('sources'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = [s for s in sources if s['title'] and '3' in s['title']]
        assert resp['paginator']['count'] == len(resultSet)
        assert len(resp['items']) == 5
        assert resp['items'][0]['id'] == resultSet[5]['id']
        assert resp['items'][-1]['id'] == resultSet[9]['id']
        assert response.content_type == 'application/json'

        # An invalid paginator (here 'page' is less than 1) will result in formencode.Invalid
        # being raised resulting in a response with a 400 status code and a JSON error msg.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'page': 0, 'itemsPerPage': 10}})
        response = self.app.request(url('sources'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

        # Some "invalid" paginators will silently fail.  For example, if there is
        # no 'pages' key, then SEARCH /sources will just assume there is no paginator
        # and all of the results will be returned.
        jsonQuery = json.dumps({
            'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'pages': 1, 'itemsPerPage': 10}})
        response = self.app.request(url('sources'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len([s for s in sources if s['title'] and '3' in s['title']])

        # Adding a 'count' key to the paginator object in the request will spare
        # the server from running query.count().  Note that the server will not
        # attempt to verify the count (since that would defeat the purpose) but
        # will simply pass it back.  The server trusts that the client is passing
        # in a factual count.  Here we pass in an inaccurate count for demonstration.
        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'page': 2, 'itemsPerPage': 4, 'count': 750}})
        response = self.app.request(url('sources'), method='SEARCH', body=jsonQuery,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['paginator']['count'] == 750
        assert len(resp['items']) == 4
        assert resp['items'][0]['id'] == resultSet[4]['id']
        assert resp['items'][-1]['id'] == resultSet[7]['id']

        # Test order by: order by title descending
        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'orderBy': ['Source', 'title', 'desc']}})
        response = self.app.post(url('/sources/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        resultSet = sorted(sources, key=lambda k: k['title'], reverse=True)
        assert len(resp) == 100
        rsIds = [s['id'] for s in resultSet]
        rsTitles = [s['title'] for s in resultSet]
        rIds = [s['id'] for s in resp]
        rTitles = [s['title'] for s in resp]
        assert [s['title'] for s in resultSet] == [s['title'] for s in resp]
        assert resp[-1]['title'] == None
        assert resp[0]['title'] == u'Title 90'
        assert response.content_type == 'application/json'

        # order by with missing direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'orderBy': ['Source', 'title']}})
        response = self.app.post(url('/sources/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[-1]['title'] == u'Title 90'
        assert resp[0]['title'] == None

        # order by with unknown direction defaults to 'asc'
        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'orderBy': ['Source', 'title', 'descending']}})
        response = self.app.post(url('/sources/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[-1]['title'] == u'Title 90'
        assert resp[0]['title'] == None

        # syntactically malformed order by
        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'orderBy': ['Source']}})
        response = self.app.post(url('/sources/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'
        assert response.content_type == 'application/json'

        # searches with lexically malformed order bys
        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'orderBy': ['Source', 'foo', 'desc']}})
        response = self.app.post(url('/sources/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Source.foo'] == u'Searching on Source.foo is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'
        assert response.content_type == 'application/json'

        jsonQuery = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'orderBy': ['Foo', 'id', 'desc']}})
        response = self.app.post(url('/sources/search'), jsonQuery,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Foo'] == u'Searching the Source model by joining on the Foo model is not possible'
        assert resp['errors']['Foo.id'] == u'Searching on Foo.id is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'
        assert response.content_type == 'application/json'

    @nottest
    def test_new_search(self):
        """Tests that GET /sources/new_search returns the search parameters for searching the sources resource."""
        queryBuilder = SQLAQueryBuilder('Source')
        response = self.app.get(url('/sources/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['searchParameters'] == h.getSearchParameters(queryBuilder)
