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
import simplejson as json
from time import sleep
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Source
from onlinelinguisticdatabase.lib.bibtex import entry_types
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder

log = logging.getLogger(__name__)

################################################################################
# Functions for creating & retrieving test data
################################################################################

today_timestamp = datetime.datetime.now()
day_delta = datetime.timedelta(1)
yesterday_timestamp = today_timestamp - day_delta

def _create_test_models(n=100):
    _add_test_models_to_session('File', n, ['name'])
    Session.commit()

def _add_test_models_to_session(model_name, n, attrs):
    for i in range(1, n + 1):
        m = getattr(model, model_name)()
        for attr in attrs:
            setattr(m, attr, u'%s %s' % (attr, i))
        Session.add(m)

def _get_test_models():
    return {'files': h.get_files()}

def _create_test_sources(n=100):
    """Create n sources with various properties.  A testing ground for searches!
    """
    files = _get_test_models()['files']

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
            s.datetime_modified = yesterday_timestamp

        Session.add(s)
    Session.commit()


def _create_test_data(n=100):
    _create_test_models(n)
    _create_test_sources(n)


class TestSourcesController(TestController):

    @nottest
    def test_index(self):
        """Tests that GET /sources returns an array of all sources and that order_by and pagination parameters work correctly."""

        # Add 100 sources.
        def create_source_from_index(index):
            source = model.Source()
            source.type = u'book'
            source.key = u'key%d' % index
            source.author = u'Chomsky, N.'
            source.title = u'Syntactic Structures %d' % index
            source.publisher = u'Mouton'
            source.year = 1957
            return source
        sources = [create_source_from_index(i) for i in range(1, 101)]
        Session.add_all(sources)
        Session.commit()
        sources = h.get_sources(True)
        sources_count = len(sources)

        # Test that GET /sources gives us all of the sources.
        extra_environ = self.extra_environ_view
        response = self.app.get(url('sources'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == sources_count
        assert resp[0]['title'] == u'Syntactic Structures 1'
        assert resp[0]['id'] == sources[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'items_per_page': 23, 'page': 3}
        response = self.app.get(url('sources'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['title'] == sources[46].title
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'Source', 'order_by_attribute': 'title',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('sources'), order_by_params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        result_set = sorted([s.title for s in sources], reverse=True)
        assert result_set == [s['title'] for s in resp]
        assert response.content_type == 'application/json'

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'Source', 'order_by_attribute': 'title',
                     'order_by_direction': 'desc', 'items_per_page': 23, 'page': 3}
        response = self.app.get(url('sources'), params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert result_set[46] == resp['items'][0]['title']

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'Source', 'order_by_attribute': 'title',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('sources'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the order_by_model/Attribute
        # param is invalid.
        order_by_params = {'order_by_model': 'Sourceful', 'order_by_attribute': 'titular',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('sources'), order_by_params,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp[0]['id'] == sources[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'items_per_page': u'a', 'page': u''}
        response = self.app.get(url('sources'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'items_per_page': 0, 'page': -1}
        response = self.app.get(url('sources'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter a number that is 1 or greater'
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
        params = self.source_create_params.copy()
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
        params = self.source_create_params.copy()
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
        sources_count = Session.query(Source).count()
        assert resp['type'] == u'book'      # the OLD converts type to lowercase
        assert resp['school'] == u'Stanford'
        assert resp['edition'] == u'second'
        assert resp['booktitle'] == u''
        assert resp['author'] == u'Noam Chomsky'
        assert response.content_type == 'application/json'

        # Attempt to create another book with the same key and expect to fail.
        params = self.source_create_params.copy()
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
        new_sources_count = Session.query(Source).count()
        assert sources_count == new_sources_count
        assert resp['errors']['key'] == u'The submitted source key is not unique'
        assert response.content_type == 'application/json'

        # Attempt to create another book with an invalid key and expect to fail.
        params = self.source_create_params.copy()
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
        new_sources_count = Session.query(Source).count()
        assert sources_count == new_sources_count
        assert resp['errors']['key'] == u'Source keys can only contain letters, numerals and symbols (except the comma)'

        # Attempt to create a book source that is invalid because it lacks a year.
        params = self.source_create_params.copy()
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
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['errors'] == \
            u'Sources of type book require values for title, publisher and year as well as a value for at least one of author and editor.'
        assert sources_count == new_sources_count
        assert response.content_type == 'application/json'

        # Attempt to create a book source that is invalid because it lacks both
        # author and editor 
        params = self.source_create_params.copy()
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
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['errors'] == \
            u'Sources of type book require values for title, publisher and year as well as a value for at least one of author and editor.'
        assert sources_count == new_sources_count
        assert response.content_type == 'application/json'

        ########################################################################
        # ARTICLE
        ########################################################################

        # Create an article; required: author, title, journal, year
        params = self.source_create_params.copy()
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
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['type'] == u'article'      # the OLD converts type to lowercase
        assert resp['title'] == u'Algonquian'
        assert resp['author'] == u'Bloomfield, L.'
        assert resp['journal'] == u'Linguistic Structures of Native America'
        assert resp['pages'] == u'85--129'
        assert resp['year'] == 1946
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'

        # Attempt to create an article without a year and expect to fail
        params = self.source_create_params.copy()
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
        sources_count = Session.query(Source).count()
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert sources_count == new_sources_count
        assert resp['errors'] == \
            u'Sources of type article require values for author, title, journal and year.'
        assert response.content_type == 'application/json'

        ########################################################################
        # BOOKLET
        ########################################################################

        # Create a booklet; required: title
        params = self.source_create_params.copy()
        params.update({
            'type': u'BOOKLET',    # case is irrelevant for entry types
            'key': u'mypoetry',
            'title': u'My Poetry (unpublished)'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['type'] == u'booklet'      # the OLD converts type to lowercase
        assert resp['title'] == u'My Poetry (unpublished)'
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'

        # Attempt to create a booklet without a title and expect to fail
        params = self.source_create_params.copy()
        params.update({
            'type': u'Booklet',    # case is irrelevant for entry types
            'key': u'mypoetry2',
            'author': 'Me Meson'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sources_count = Session.query(Source).count()
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert sources_count == new_sources_count
        assert resp['errors'] == \
            u'Sources of type booklet require a value for title.'
        assert response.content_type == 'application/json'

        ########################################################################
        # INBOOK
        ########################################################################

        # Create an inbook; required: title, publisher, year and one of author
        # or editor and one of chapter or pages.
        params = self.source_create_params.copy()
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
        inbook_id = resp['id']
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['type'] == u'inbook'      # the OLD converts type to lowercase
        assert resp['title'] == u'Linguistics in Philosophy'
        assert resp['publisher'] == u'Cornell University Press'
        assert resp['year'] == 1967
        assert resp['author'] == u'Vendler, Zeno'
        assert resp['chapter'] == u'4'
        assert resp['pages'] == u''
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'

        # Attempt to create an inbook without a chapter or pages and expect to fail
        params = self.source_create_params.copy()
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
        sources_count = Session.query(Source).count()
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert sources_count == new_sources_count
        assert resp['errors'] == \
            u'Sources of type inbook require values for title, publisher and year as well as a value for at least one of author and editor and at least one of chapter and pages.'
        assert response.content_type == 'application/json'

        # 'required': (('author', 'editor'), 'title', ('chapter', 'pages'), 'publisher', 'year')
        # Create a book that the inbook above will cross-reference once updated.
        # required: author or editor, title, publisher and year
        params = self.source_create_params.copy()
        params.update({
            'type': u'bOOk',    # case is irrelevant for entry types
            'key': u'vendler67book',
            'author': u'Vendler, Zeno',
            'title': u'Linguistics in Philosophy',
            'publisher': u'Cornell University Press',
            'year': 1967
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['type'] == u'book'      # the OLD converts type to lowercase
        assert resp['title'] == u'Linguistics in Philosophy'
        assert resp['author'] == u'Vendler, Zeno'
        assert resp['year'] == 1967
        assert resp['publisher'] == u'Cornell University Press'
        assert resp['key'] == u'vendler67book'
        assert response.content_type == 'application/json'

        # Now update the valid inbook created above and have it cross-reference
        # the book just created above.  Because the Vendler book has all of the
        # rest of the attributes, all we need to specify is the chapter.
        params = self.source_create_params.copy()
        params.update({
            'type': u'inbook',    # case is irrelevant for entry types
            'key': u'vendler67',
            'chapter': u'4',
            'crossref': u'vendler67book'
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=inbook_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['type'] == u'inbook'      # the OLD converts type to lowercase
        assert resp['crossref_source']['title'] == u'Linguistics in Philosophy'
        assert resp['crossref_source']['publisher'] == u'Cornell University Press'
        assert resp['crossref_source']['year'] == 1967
        assert resp['crossref_source']['author'] == u'Vendler, Zeno'
        assert resp['chapter'] == u'4'

        # Now update our inbook back to how it was and remove the cross-reference;
        # make sure that the crossref_source value is now None.
        params = self.source_create_params.copy()
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
        response = self.app.put(url('source', id=inbook_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['type'] == u'inbook'      # the OLD converts type to lowercase
        assert resp['title'] == u'Linguistics in Philosophy'
        assert resp['publisher'] == u'Cornell University Press'
        assert resp['year'] == 1967
        assert resp['author'] == u'Vendler, Zeno'
        assert resp['chapter'] == u'4'
        assert resp['pages'] == u''
        assert resp['crossref'] == u''
        assert resp['crossref_source'] == None
        assert new_sources_count == sources_count
        assert response.content_type == 'application/json'


        ########################################################################
        # MISC
        ########################################################################

        # Create a misc; required: nothing.
        params = self.source_create_params.copy()
        params.update({
            'type': u'misc',    # case is irrelevant for entry types
            'key': u'manuel83',
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert resp['type'] == u'misc'      # the OLD converts type to lowercase
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'

        ########################################################################
        # INPROCEEDINGS
        ########################################################################

        # Create an inproceedings; required: author, title, booktitle, year.
        params = self.source_create_params.copy()
        params.update({
            'type': u'inpROceedings',    # case is irrelevant for entry types
            'key': u'oaho83',
            'title': u'On Notions of Information Transfer in {VLSI} Circuits',
            'booktitle': u'Proc. Fifteenth Annual ACM',
            'year': 1983,
            'author': u'Alfred V. Oaho and Jeffrey D. Ullman and Mihalis Yannakakis'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        inproceedings_id = resp['id']
        assert resp['type'] == u'inproceedings'      # the OLD converts type to lowercase
        assert resp['title'] == u'On Notions of Information Transfer in {VLSI} Circuits'
        assert resp['booktitle'] == u'Proc. Fifteenth Annual ACM'
        assert resp['year'] == 1983
        assert resp['author'] == u'Alfred V. Oaho and Jeffrey D. Ullman and Mihalis Yannakakis'
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'

        # Attempt to create an inproceedings that lacks booktitle and year
        # values; expect to fail.
        params = self.source_create_params.copy()
        params.update({
            'type': u'inpROceedings',    # case is irrelevant for entry types
            'key': u'oaho83_2',
            'title': u'On Notions of Information Transfer in {VLSI} Circuits',
            'author': 'Alfred V. Oaho and Jeffrey D. Ullman and Mihalis Yannakakis'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert new_sources_count == sources_count
        assert response.content_type == 'application/json'
        assert resp['errors'] == u'Sources of type inproceedings require values for author, title, booktitle and year.'

        # Now create a proceedings source that will be cross-referenced by the
        # above inproceedings source.
        params = self.source_create_params.copy()
        params.update({
            'type': u'PROceedings',    # case is irrelevant for entry types
            'key': u'acm15_83',
            'title': u'Proc. Fifteenth Annual',
            'booktitle': u'Proc. Fifteenth Annual ACM',
            'year': 1983
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        proceedings_id = resp['id']
        assert resp['type'] == u'proceedings'      # the OLD converts type to lowercase
        assert resp['title'] == u'Proc. Fifteenth Annual'
        assert resp['booktitle'] == u'Proc. Fifteenth Annual ACM'
        assert resp['year'] == 1983
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'

        # Now attempt to create an inproceedings that lacks booktitle and year
        # values but cross-reference the proceedings source we just created; expect to succeed.
        params = self.source_create_params.copy()
        params.update({
            'type': u'inpROceedings',    # case is irrelevant for entry types
            'key': u'oaho83_2',
            'title': u'On Notions of Information Transfer in {VLSI} Circuits',
            'author': u'Alfred V. Oaho and Jeffrey D. Ullman and Mihalis Yannakakis',
            'crossref': u'acm15_83'
        })
        params = json.dumps(params)
        response = self.app.post(url('sources'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'
        assert resp['type'] == u'inproceedings'      # the OLD converts type to lowercase
        assert resp['title'] == u'On Notions of Information Transfer in {VLSI} Circuits'
        assert resp['crossref_source']['booktitle'] == u'Proc. Fifteenth Annual ACM'
        assert resp['crossref_source']['year'] == 1983
        assert resp['author'] == u'Alfred V. Oaho and Jeffrey D. Ullman and Mihalis Yannakakis'
        assert new_sources_count == sources_count + 1
        assert response.content_type == 'application/json'
        assert resp['crossref_source']['id'] == proceedings_id

        # Make sure the crossref stuff works with updates
        params = self.source_create_params.copy()
        params.update({
            'type': u'inpROceedings',    # case is irrelevant for entry types
            'key': u'oaho83',
            'title': u'On Notions of Information Transfer in {VLSI} Circuits',
            'author': u'Alfred V. Oaho and Jeffrey D. Ullman and Mihalis Yannakakis',
            'crossref': u'acm15_83'
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=inproceedings_id), params,
                                self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        sources_count = new_sources_count
        new_sources_count = Session.query(Source).count()
        assert response.content_type == 'application/json'
        assert resp['type'] == u'inproceedings'      # the OLD converts type to lowercase
        assert resp['title'] == u'On Notions of Information Transfer in {VLSI} Circuits'
        assert resp['crossref_source']['booktitle'] == u'Proc. Fifteenth Annual ACM'
        assert resp['crossref_source']['year'] == 1983
        assert resp['author'] == u'Alfred V. Oaho and Jeffrey D. Ullman and Mihalis Yannakakis'
        assert new_sources_count == sources_count
        assert response.content_type == 'application/json'
        assert resp['crossref_source']['id'] == proceedings_id

    @nottest
    def test_new(self):
        """Tests that GET /sources/new returns the list of valid BibTeX entry types."""
        response = self.app.get(url('new_source'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['types'] == sorted(entry_types.keys())
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /sources/1 updates an existing source."""

        # Create a book to update.
        params = self.source_create_params.copy()
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
        source_count = Session.query(Source).count()
        book_id = resp['id']
        original_datetime_modified = resp['datetime_modified']

        # Update the book
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetime_modified for the update
        params = self.source_create_params.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Chomsky, N.',   # Change the format of the author
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=book_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetime_modified = resp['datetime_modified']
        new_source_count = Session.query(Source).count()
        assert source_count == new_source_count
        assert datetime_modified != original_datetime_modified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        params = self.source_create_params.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Chomsky, N.',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=book_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        source_count = new_source_count
        new_source_count = Session.query(Source).count()
        our_book_datetime_modified = Session.query(Source).get(book_id).datetime_modified
        assert our_book_datetime_modified.isoformat() == datetime_modified
        assert source_count == new_source_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Update by adding a file to the source
        file_ = h.generate_default_file()
        Session.add(file_)
        Session.commit()
        file_id = file_.id
        filename = file_.name

        sleep(1)    # sleep for a second to ensure that MySQL can register a different datetime_modified for the update
        params = self.source_create_params.copy()
        params.update({
            'type': u'book',
            'key': u'chomsky57',
            'author': u'Chomsky, N.',
            'title': u'Syntactic Structures',
            'publisher': u'Mouton',
            'year': 1957,
            'file': file_id
        })
        params = json.dumps(params)
        response = self.app.put(url('source', id=book_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        source_count = new_source_count
        new_source_count = Session.query(Source).count()
        new_datetime_modified = resp['datetime_modified']
        assert new_datetime_modified != datetime_modified
        assert source_count == new_source_count
        assert resp['file']['name'] == filename
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /sources/id deletes the source with id=id."""

        # Create a book to delete.
        params = self.source_create_params.copy()
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
        source_count = Session.query(Source).count()
        book_id = resp['id']

        # Now delete the source
        response = self.app.delete(url('source', id=book_id), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        new_source_count = Session.query(Source).count()
        assert new_source_count == source_count - 1
        assert resp['id'] == book_id
        assert response.content_type == 'application/json'

        # Trying to get the deleted source from the db should return None
        deleted_source = Session.query(Source).get(book_id)
        assert deleted_source == None

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
        params = self.source_create_params.copy()
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
        book_id = resp['id']

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
        response = self.app.get(url('source', id=book_id), headers=self.json_headers,
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
        params = self.source_create_params.copy()
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
        book_id = resp['id']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_source', id=book_id), status=401)
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
        response = self.app.get(url('edit_source', id=book_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['source']['title'] == u'Syntactic Structures'
        assert resp['data']['types'] == sorted(entry_types.keys())
        assert response.content_type == 'application/json'

    @nottest
    def test_search(self):
        """Tests that SEARCH /sources (a.k.a. POST /sources/search) correctly returns an array of sources based on search criteria."""

        # Create some sources (and other models) to search and add SEARCH to the list of allowable methods
        _create_test_data(100)
        self._add_SEARCH_to_web_test_valid_methods()

        sources = json.loads(json.dumps(h.get_sources(True), cls=h.JSONOLDEncoder))

        # Searching where values may be NULL
        json_query = json.dumps({'query': {'filter': ['Source', 'publisher', '=', None]}})
        response = self.app.post(url('/sources/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [s for s in sources if not s['publisher']]
        assert resp
        assert len(resp) == len(result_set)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in result_set])
        assert response.content_type == 'application/json'

        json_query = json.dumps({'query': {'filter': ['Source', 'publisher', 'like', u'%P%']}})
        response = self.app.post(url('/sources/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [s for s in sources if s['publisher'] and u'P' in s['publisher']]
        assert resp
        assert len(resp) == len(result_set)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in result_set])
        assert response.content_type == 'application/json'

        # A fairly complex search
        json_query = json.dumps({'query': {'filter': [
            'and', [
                ['Source', 'type', 'in', [u'book', u'article']],
                ['not', ['Source', 'key', 'regex', u'[537]']],
                ['or', [
                    ['Source', 'author', 'like', u'%A%'],
                    ['Source', 'year', '>', 1994]]]]]}})
        response = self.app.post(url('/sources/search'), json_query,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [s for s in sources if
            s['type'] in ['book', 'article'] and
            not re.search('[537]', s['key']) and
            ('A' in s['author'] or s['year'] > 1994)]
        assert resp
        assert len(resp) == len(result_set)
        assert set([s['id'] for s in resp]) == set([s['id'] for s in result_set])
        assert response.content_type == 'application/json'

        # A basic search with a paginator provided.
        json_query = json.dumps({'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'page': 2, 'items_per_page': 5}})
        response = self.app.request(url('sources'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = [s for s in sources if s['title'] and '3' in s['title']]
        assert resp['paginator']['count'] == len(result_set)
        assert len(resp['items']) == 5
        assert resp['items'][0]['id'] == result_set[5]['id']
        assert resp['items'][-1]['id'] == result_set[9]['id']
        assert response.content_type == 'application/json'

        # An invalid paginator (here 'page' is less than 1) will result in formencode.Invalid
        # being raised resulting in a response with a 400 status code and a JSON error msg.
        json_query = json.dumps({
            'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'page': 0, 'items_per_page': 10}})
        response = self.app.request(url('sources'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

        # Some "invalid" paginators will silently fail.  For example, if there is
        # no 'pages' key, then SEARCH /sources will just assume there is no paginator
        # and all of the results will be returned.
        json_query = json.dumps({
            'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'pages': 1, 'items_per_page': 10}})
        response = self.app.request(url('sources'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len([s for s in sources if s['title'] and '3' in s['title']])

        # Adding a 'count' key to the paginator object in the request will spare
        # the server from running query.count().  Note that the server will not
        # attempt to verify the count (since that would defeat the purpose) but
        # will simply pass it back.  The server trusts that the client is passing
        # in a factual count.  Here we pass in an inaccurate count for demonstration.
        json_query = json.dumps({'query': {
                'filter': ['Source', 'title', 'like', '%3%']},
            'paginator': {'page': 2, 'items_per_page': 4, 'count': 750}})
        response = self.app.request(url('sources'), method='SEARCH', body=json_query,
            headers=self.json_headers, environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['paginator']['count'] == 750
        assert len(resp['items']) == 4
        assert resp['items'][0]['id'] == result_set[4]['id']
        assert resp['items'][-1]['id'] == result_set[7]['id']

        # Test order by: order by title descending
        json_query = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'order_by': ['Source', 'title', 'desc']}})
        response = self.app.post(url('/sources/search'), json_query,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        result_set = sorted(sources, key=lambda k: k['title'], reverse=True)
        assert len(resp) == 100
        assert [s['title'] for s in result_set] == [s['title'] for s in resp]
        assert resp[-1]['title'] == None
        assert resp[0]['title'] == u'Title 90'
        assert response.content_type == 'application/json'

        # order by with missing direction defaults to 'asc'
        json_query = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'order_by': ['Source', 'title']}})
        response = self.app.post(url('/sources/search'), json_query,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[-1]['title'] == u'Title 90'
        assert resp[0]['title'] == None

        # order by with unknown direction defaults to 'asc'
        json_query = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'order_by': ['Source', 'title', 'descending']}})
        response = self.app.post(url('/sources/search'), json_query,
            self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[-1]['title'] == u'Title 90'
        assert resp[0]['title'] == None

        # syntactically malformed order by
        json_query = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'order_by': ['Source']}})
        response = self.app.post(url('/sources/search'), json_query,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'
        assert response.content_type == 'application/json'

        # searches with lexically malformed order bys
        json_query = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'order_by': ['Source', 'foo', 'desc']}})
        response = self.app.post(url('/sources/search'), json_query,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Source.foo'] == u'Searching on Source.foo is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'
        assert response.content_type == 'application/json'

        json_query = json.dumps({'query': {
                'filter': ['Source', 'key', 'regex', '.'],
                'order_by': ['Foo', 'id', 'desc']}})
        response = self.app.post(url('/sources/search'), json_query,
            self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['Foo'] == u'Searching the Source model by joining on the Foo model is not possible'
        assert resp['errors']['Foo.id'] == u'Searching on Foo.id is not permitted'
        assert resp['errors']['OrderByError'] == u'The provided order by expression was invalid.'
        assert response.content_type == 'application/json'

    @nottest
    def test_new_search(self):
        """Tests that GET /sources/new_search returns the search parameters for searching the sources resource."""
        query_builder = SQLAQueryBuilder('Source')
        response = self.app.get(url('/sources/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['search_parameters'] == h.get_search_parameters(query_builder)
