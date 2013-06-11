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

import logging
import simplejson as json
from time import sleep
from nose.tools import nottest
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Page

log = logging.getLogger(__name__)

################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestPagesController(TestController):
    
    md_contents = u'\n'.join([
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

    @nottest
    def test_index(self):
        """Tests that GET /pages returns an array of all pages and that order_by and pagination parameters work correctly."""

        # Add 100 pages.
        def create_page_from_index(index):
            page = model.Page()
            page.name = u'page%d' % index
            page.markup_language = u'Markdown'
            page.content = self.md_contents
            return page
        pages = [create_page_from_index(i) for i in range(1, 101)]
        Session.add_all(pages)
        Session.commit()
        pages = h.get_pages(True)
        pages_count = len(pages)

        # Test that GET /pages gives us all of the pages.
        response = self.app.get(url('pages'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == pages_count
        assert resp[0]['name'] == u'page1'
        assert resp[0]['id'] == pages[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'items_per_page': 23, 'page': 3}
        response = self.app.get(url('pages'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == pages[46].name
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'Page', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('pages'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        result_set = sorted([p.name for p in pages], reverse=True)
        assert result_set == [p['name'] for p in resp]

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'Page', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc', 'items_per_page': 23, 'page': 3}
        response = self.app.get(url('pages'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert result_set[46] == resp['items'][0]['name']

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'Page', 'order_by_attribute': 'name',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('pages'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the order_by_model/Attribute
        # param is invalid.
        order_by_params = {'order_by_model': 'Pageist', 'order_by_attribute': 'nominal',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('pages'), order_by_params,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == pages[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'items_per_page': u'a', 'page': u''}
        response = self.app.get(url('pages'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'items_per_page': 0, 'page': -1}
        response = self.app.get(url('pages'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /pages creates a new page
        or returns an appropriate error if the input is invalid.
        """

        original_page_count = Session.query(Page).count()

        # Create a valid one
        params = self.page_create_params.copy()
        params.update({
            'name': u'page',
            'markup_language': u'Markdown',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_page_count = Session.query(Page).count()
        assert new_page_count == original_page_count + 1
        assert resp['name'] == u'page'
        assert resp['content'] == self.md_contents
        assert resp['html'] == h.get_HTML_from_contents(self.md_contents, 'Markdown')
        assert response.content_type == 'application/json'

        # Invalid because name is empty and markup language is invalid
        params = self.page_create_params.copy()
        params.update({
            'name': u'',
            'markup_language': u'markdownable',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'
        assert resp['errors']['markup_language'] == \
            u"Value must be one of: Markdown; reStructuredText (not u'markdownable')"
        assert response.content_type == 'application/json'

        # Invalid because name is too long
        params = self.page_create_params.copy()
        params.update({
            'name': u'name' * 200,
            'markup_language': u'Markdown',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    @nottest
    def test_new(self):
        """Tests that GET /pages/new returns the list of accepted markup languages."""
        response = self.app.get(url('new_page'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {'markup_languages': list(h.markup_languages)}
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /pages/id updates the page with id=id."""

        # Create a page to update.
        params = self.page_create_params.copy()
        params.update({
            'name': u'page',
            'markup_language': u'Markdown',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        page_count = Session.query(Page).count()
        page_id = resp['id']
        original_datetime_modified = resp['datetime_modified']

        # Update the page
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetime_modified for the update
        params = self.page_create_params.copy()
        params.update({
            'name': u'Awesome Page',
            'markup_language': u'Markdown',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.put(url('page', id=page_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetime_modified = resp['datetime_modified']
        new_page_count = Session.query(Page).count()
        assert page_count == new_page_count
        assert datetime_modified != original_datetime_modified
        assert resp['name'] == u'Awesome Page'
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        response = self.app.put(url('page', id=page_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        page_count = new_page_count
        new_page_count = Session.query(Page).count()
        our_page_datetime_modified = Session.query(Page).get(page_id).datetime_modified
        assert our_page_datetime_modified.isoformat() == datetime_modified
        assert page_count == new_page_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /pages/id deletes the page with id=id."""

        # Create a page to delete.
        params = self.page_create_params.copy()
        params.update({
            'name': u'page',
            'markup_language': u'Markdown',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        page_count = Session.query(Page).count()
        page_id = resp['id']

        # Now delete the page
        response = self.app.delete(url('page', id=page_id), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        new_page_count = Session.query(Page).count()
        assert new_page_count == page_count - 1
        assert resp['id'] == page_id
        assert response.content_type == 'application/json'

        # Trying to get the deleted page from the db should return None
        deleted_page = Session.query(Page).get(page_id)
        assert deleted_page == None
        assert response.content_type == 'application/json'

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('page', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no page with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('page', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

    @nottest
    def test_show(self):
        """Tests that GET /pages/id returns the page with id=id or an appropriate error."""

        # Create a page to show.
        params = self.page_create_params.copy()
        params.update({
            'name': u'page',
            'markup_language': u'Markdown',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        page_id = resp['id']

        # Try to get a page using an invalid id
        id = 100000000000
        response = self.app.get(url('page', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no page with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('page', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('page', id=page_id), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'page'
        assert resp['content'] == self.md_contents
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /pages/id/edit returns a JSON object of data necessary to edit the page with id=id.

        The JSON object is of the form {'page': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a page to edit.
        params = self.page_create_params.copy()
        params.update({
            'name': u'page',
            'markup_language': u'Markdown',
            'content': self.md_contents
        })
        params = json.dumps(params)
        response = self.app.post(url('pages'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        page_id = resp['id']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_page', id=page_id), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_page', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no page with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_page', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_page', id=page_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['page']['name'] == u'page'
        assert resp['data'] == {'markup_languages': list(h.markup_languages)}
        assert response.content_type == 'application/json'
