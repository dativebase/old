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
from old.tests import *
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h
from old.model import Page
from old.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestPagesController(TestController):
    
    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    mdContents = u'\n'.join([
        'My Page',
        '=======',
        '',
        'Research Interests',
        '---------------------',
        '',
        '* Item 1',
        '* Item 2',
        ''
    ])

    createParams = {
        'name': u'',
        'heading': u'',
        'markupLanguage': u'',
        'content': u'',
        'html': u''
    }

    # Clear all models in the database except Language; recreate the users.
    def tearDown(self):
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that GET /pages returns an array of all pages and that orderBy and pagination parameters work correctly."""

        # Add 100 pages.
        def createPageFromIndex(index):
            page = model.Page()
            page.name = u'page%d' % index
            page.markupLanguage = u'markdown'
            page.content = self.mdContents
            return page
        pages = [createPageFromIndex(i) for i in range(1, 101)]
        Session.add_all(pages)
        Session.commit()
        pages = h.getPages(True)
        pagesCount = len(pages)

        # Test that GET /pages gives us all of the pages.
        response = self.app.get(url('pages'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == pagesCount
        assert resp[0]['name'] == u'page1'
        assert resp[0]['id'] == pages[0].id

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('pages'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == pages[46].name

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Page', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('pages'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted([p.name for p in pages], reverse=True)
        assert resultSet == [p['name'] for p in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Page', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('pages'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['name']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Page', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('pages'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Pageist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('pages'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == pages[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('pages'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('pages'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

    #@nottest
    def test_create(self):
        """Tests that POST /pages creates a new page
        or returns an appropriate error if the input is invalid.
        """

        originalPageCount = Session.query(Page).count()

        # Create a valid one
        params = self.createParams.copy()
        params.update({
            'name': u'page',
            'markupLanguage': u'markdown',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newPageCount = Session.query(Page).count()
        assert newPageCount == originalPageCount + 1
        assert resp['name'] == u'page'
        assert resp['content'] == self.mdContents
        assert resp['html'] == h.getHTMLFromContents(self.mdContents, 'markdown')

        # Invalid because name is empty and markup language is invalid
        params = self.createParams.copy()
        params.update({
            'name': u'',
            'markupLanguage': u'markdownable',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'
        assert resp['errors']['markupLanguage'] == \
            u"Value must be one of: markdown; reStructuredText (not u'markdownable')"

        # Invalid because name is too long
        params = self.createParams.copy()
        params.update({
            'name': u'name' * 200,
            'markupLanguage': u'markdown',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

    #@nottest
    def test_new(self):
        """Tests that GET /pages/new returns the list of accepted markup languages."""
        response = self.app.get(url('new_page'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {'markupLanguages': list(h.markupLanguages)}

    #@nottest
    def test_update(self):
        """Tests that PUT /pages/id updates the page with id=id."""

        # Create a page to update.
        params = self.createParams.copy()
        params.update({
            'name': u'page',
            'markupLanguage': u'markdown',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        pageCount = Session.query(Page).count()
        pageId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Update the page
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'name': u'Awesome Page',
            'markupLanguage': u'markdown',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.put(url('page', id=pageId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newPageCount = Session.query(Page).count()
        assert pageCount == newPageCount
        assert datetimeModified != originalDatetimeModified
        assert resp['name'] == u'Awesome Page'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('page', id=pageId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        pageCount = newPageCount
        newPageCount = Session.query(Page).count()
        ourPageDatetimeModified = Session.query(Page).get(pageId).datetimeModified
        assert ourPageDatetimeModified.isoformat() == datetimeModified
        assert pageCount == newPageCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /pages/id deletes the page with id=id."""

        # Create a page to delete.
        params = self.createParams.copy()
        params.update({
            'name': u'page',
            'markupLanguage': u'markdown',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        pageCount = Session.query(Page).count()
        pageId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Now delete the page
        response = self.app.delete(url('page', id=pageId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newPageCount = Session.query(Page).count()
        assert newPageCount == pageCount - 1
        assert resp['id'] == pageId

        # Trying to get the deleted page from the db should return None
        deletedPage = Session.query(Page).get(pageId)
        assert deletedPage == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('page', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no page with id %s' % id in json.loads(response.body)['error']

        # Delete without an id
        response = self.app.delete(url('page', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

    #@nottest
    def test_show(self):
        """Tests that GET /pages/id returns the page with id=id or an appropriate error."""

        # Create a page to show.
        params = self.createParams.copy()
        params.update({
            'name': u'page',
            'markupLanguage': u'markdown',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        pageCount = Session.query(Page).count()
        pageId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Try to get a page using an invalid id
        id = 100000000000
        response = self.app.get(url('page', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no page with id %s' % id in json.loads(response.body)['error']

        # No id
        response = self.app.get(url('page', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

        # Valid id
        response = self.app.get(url('page', id=pageId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'page'
        assert resp['content'] == self.mdContents

    #@nottest
    def test_edit(self):
        """Tests that GET /pages/id/edit returns a JSON object of data necessary to edit the page with id=id.

        The JSON object is of the form {'page': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a page to edit.
        params = self.createParams.copy()
        params.update({
            'name': u'page',
            'markupLanguage': u'markdown',
            'content': self.mdContents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        pageCount = Session.query(Page).count()
        pageId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_page', id=pageId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_page', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no page with id %s' % id in json.loads(response.body)['error']

        # No id
        response = self.app.get(url('edit_page', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_page', id=pageId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['page']['name'] == u'page'
        assert resp['data'] == {'markupLanguages': list(h.markupLanguages)}
