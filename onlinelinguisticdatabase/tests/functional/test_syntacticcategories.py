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
from onlinelinguisticdatabase.model import SyntacticCategory

log = logging.getLogger(__name__)

################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestSyntacticcategoriesController(TestController):

    @nottest
    def test_index(self):
        """Tests that GET /syntacticcategories returns an array of all syntactic categories and that order_by and pagination parameters work correctly."""

        # Add 100 syntactic categories.
        def create_syntactic_category_from_index(index):
            syntactic_category = model.SyntacticCategory()
            syntactic_category.name = u'sc%d' % index
            syntactic_category.type = u'lexical'
            syntactic_category.description = u'description %d' % index
            return syntactic_category
        syntactic_categories = [create_syntactic_category_from_index(i) for i in range(1, 101)]
        Session.add_all(syntactic_categories)
        Session.commit()
        syntactic_categories = h.get_syntactic_categories(True)
        syntactic_categories_count = len(syntactic_categories)

        # Test that GET /syntacticcategories gives us all of the syntactic categories.
        response = self.app.get(url('syntacticcategories'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == syntactic_categories_count
        assert resp[0]['name'] == u'sc1'
        assert resp[0]['id'] == syntactic_categories[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'items_per_page': 23, 'page': 3}
        response = self.app.get(url('syntacticcategories'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == syntactic_categories[46].name
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'SyntacticCategory', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('syntacticcategories'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        result_set = sorted([sc.name for sc in syntactic_categories], reverse=True)
        assert result_set == [sc['name'] for sc in resp]

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'SyntacticCategory', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc', 'items_per_page': 23, 'page': 3}
        response = self.app.get(url('syntacticcategories'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert result_set[46] == resp['items'][0]['name']
        assert response.content_type == 'application/json'

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'SyntacticCategory', 'order_by_attribute': 'name',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('syntacticcategories'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the order_by_model/Attribute
        # param is invalid.
        order_by_params = {'order_by_model': 'SyntacticCategoryist', 'order_by_attribute': 'nominal',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('syntacticcategories'), order_by_params,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == syntactic_categories[0].id
        assert response.content_type == 'application/json'

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'items_per_page': u'a', 'page': u''}
        response = self.app.get(url('syntacticcategories'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'items_per_page': 0, 'page': -1}
        response = self.app.get(url('syntacticcategories'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /syntacticcategories creates a new syntactic category
        or returns an appropriate error if the input is invalid.
        """

        original_SC_count = Session.query(SyntacticCategory).count()

        # Create a valid one
        params = json.dumps({'name': u'sc', 'type': u'lexical', 'description': u'Described.'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_SC_count = Session.query(SyntacticCategory).count()
        assert new_SC_count == original_SC_count + 1
        assert resp['name'] == u'sc'
        assert resp['description'] == u'Described.'
        assert resp['type'] == u'lexical'
        assert response.content_type == 'application/json'

        # Invalid because name is not unique
        params = json.dumps({'name': u'sc', 'type': u'lexical', 'description': u'Described.'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'The submitted value for SyntacticCategory.name is not unique.'
        assert response.content_type == 'application/json'

        # Invalid because name is empty
        params = json.dumps({'name': u'', 'type': u'lexical', 'description': u'Described.'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Please enter a value'

        # Invalid because name is too long
        params = json.dumps({'name': u'name' * 400, 'type': u'lexical', 'description': u'Described.'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

        # Invalid because type is not in utils.syntactic_category_types
        params = json.dumps({'name': u'name' * 400, 'type': u'spatial', 'description': u'Described.'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['type'] == u"Value must be one of: lexical; phrasal; sentential (not u'spatial')"
        assert response.content_type == 'application/json'

    @nottest
    def test_new(self):
        """Tests that GET /syntacticcategories/new returns an empty JSON object."""
        response = self.app.get(url('new_syntacticcategory'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['syntactic_category_types'] == list(h.syntactic_category_types)
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /syntacticcategories/id updates the syntacticcategory with id=id."""

        # Create an syntactic category to update.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntactic_category_count = Session.query(SyntacticCategory).count()
        syntactic_category_id = resp['id']
        original_datetime_modified = resp['datetime_modified']

        # Update the syntactic category
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetime_modified for the update
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'More content-ful description.'})
        response = self.app.put(url('syntacticcategory', id=syntactic_category_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetime_modified = resp['datetime_modified']
        new_syntactic_category_count = Session.query(SyntacticCategory).count()
        assert syntactic_category_count == new_syntactic_category_count
        assert datetime_modified != original_datetime_modified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        response = self.app.put(url('syntacticcategory', id=syntactic_category_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        syntactic_category_count = new_syntactic_category_count
        new_syntactic_category_count = Session.query(SyntacticCategory).count()
        our_SC_datetime_modified = Session.query(SyntacticCategory).get(syntactic_category_id).datetime_modified
        assert our_SC_datetime_modified.isoformat() == datetime_modified
        assert syntactic_category_count == new_syntactic_category_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /syntacticcategories/id deletes the syntactic_category with id=id."""

        # Create an syntactic category to delete.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntactic_category_count = Session.query(SyntacticCategory).count()
        syntactic_category_id = resp['id']

        # Now delete the syntactic category
        response = self.app.delete(url('syntacticcategory', id=syntactic_category_id), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        new_syntactic_category_count = Session.query(SyntacticCategory).count()
        assert new_syntactic_category_count == syntactic_category_count - 1
        assert resp['id'] == syntactic_category_id
        assert response.content_type == 'application/json'

        # Trying to get the deleted syntactic category from the db should return None
        deleted_syntactic_category = Session.query(SyntacticCategory).get(syntactic_category_id)
        assert deleted_syntactic_category == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('syntacticcategory', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no syntactic category with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('syntacticcategory', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    @nottest
    def test_show(self):
        """Tests that GET /syntacticcategories/id returns the syntactic category with id=id or an appropriate error."""

        # Create an syntactic category to show.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntactic_category_id = resp['id']

        # Try to get a syntactic_category using an invalid id
        id = 100000000000
        response = self.app.get(url('syntacticcategory', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no syntactic category with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('syntacticcategory', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('syntacticcategory', id=syntactic_category_id), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'name'
        assert resp['description'] == u'description'
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /syntacticcategories/id/edit returns a JSON object of data necessary to edit the syntactic category with id=id.

        The JSON object is of the form {'syntactic_category': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create an syntactic category to edit.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntactic_category_id = resp['id']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_syntacticcategory', id=syntactic_category_id), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_syntacticcategory', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no syntactic category with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_syntacticcategory', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_syntacticcategory', id=syntactic_category_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['syntactic_category']['name'] == u'name'
        assert resp['data']['syntactic_category_types'] == list(h.syntactic_category_types)
        assert response.content_type == 'application/json'


    @nottest
    def test_category_percolation(self):
        """Tests that changes to a category's name and deletion of a category trigger updates to forms containing morphemes of that category.
        """

        application_settings = h.generate_default_application_settings()
        Session.add(application_settings)
        Session.commit()

        extra_environ = {'test.authentication.role': u'administrator',
                               'test.application_settings': True}

        # Create an N category
        params = json.dumps({'name': u'N', 'type': u'lexical', 'description': u''})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        NId = resp['id']
        assert resp['name'] == u'N'
        assert response.content_type == 'application/json'

        # Create a lexical form 'chien/dog' of category N
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'chien',
            'morpheme_break': u'chien',
            'morpheme_gloss': u'dog',
            'translations': [{'transcription': u'dog', 'grammaticality': u''}],
            'syntactic_category': NId
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, extra_environ)
        resp = json.loads(response.body)
        chien_id = resp['id']
        assert resp['morpheme_break_ids'][0][0][0][1] == u'dog'
        assert resp['morpheme_break_ids'][0][0][0][2] == u'N'
        assert resp['morpheme_gloss_ids'][0][0][0][1] == u'chien'
        assert resp['morpheme_gloss_ids'][0][0][0][2] == u'N'
        assert resp['syntactic_category_string'] == u'N'
        assert resp['break_gloss_category'] == u'chien|dog|N'

        # Create a phrasal form 'chien-s/dog-PL' that will contain 'chien/dog'
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'chiens',
            'morpheme_break': u'chien-s',
            'morpheme_gloss': u'dog-PL',
            'translations': [{'transcription': u'dogs', 'grammaticality': u''}],
            'syntactic_category': NId
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, extra_environ)
        resp = json.loads(response.body)
        chiens_id = resp['id']
        assert resp['morpheme_break_ids'][0][0][0][1] == u'dog'
        assert resp['morpheme_break_ids'][0][0][0][2] == u'N'
        assert resp['morpheme_gloss_ids'][0][0][0][1] == u'chien'
        assert resp['morpheme_gloss_ids'][0][0][0][2] == u'N'
        assert resp['syntactic_category_string'] == u'N-?'
        assert resp['break_gloss_category'] == u'chien|dog|N-s|PL|?'

        # Now update the name of the N category and expect that change to cause
        # an update to the chien/dog and chien-s/dog-PL forms.
        form_backup_count = Session.query(model.FormBackup).count()
        params = json.dumps({'name': u'Noun', 'type': u'lexical', 'description': u''})
        response = self.app.put(url('syntacticcategory', id=NId), params, self.json_headers, extra_environ)
        new_form_backup_count = Session.query(model.FormBackup).count()
        chien = Session.query(model.Form).get(chien_id)
        chiens = Session.query(model.Form).get(chiens_id)
        assert new_form_backup_count == form_backup_count + 2
        assert chien.syntactic_category_string == u'Noun'
        assert chiens.syntactic_category_string == u'Noun-?'
        assert json.loads(chiens.morpheme_break_ids)[0][0][0][2] == u'Noun'

        # Now update something besides the name attribute of the N/Noun category
        # and expect no updates to any forms.
        params = json.dumps({'name': u'Noun', 'type': u'lexical', 'description': u'Blah!'})
        response = self.app.put(url('syntacticcategory', id=NId), params, self.json_headers, extra_environ)
        form_backup_count = new_form_backup_count
        new_form_backup_count = Session.query(model.FormBackup).count()
        chien = chiens = None
        chien = Session.query(model.Form).get(chien_id)
        chiens = Session.query(model.Form).get(chiens_id)
        assert new_form_backup_count == form_backup_count
        assert chien.syntactic_category_string == u'Noun'
        assert chiens.syntactic_category_string == u'Noun-?'
        assert json.loads(chiens.morpheme_break_ids)[0][0][0][2] == u'Noun'

        # Test deletion of sc
        response = self.app.delete(url('syntacticcategory', id=NId), headers=self.json_headers,
                                   extra_environ=extra_environ)
        form_backup_count = new_form_backup_count
        new_form_backup_count = Session.query(model.FormBackup).count()
        chien = chiens = None
        chien = Session.query(model.Form).get(chien_id)
        chiens = Session.query(model.Form).get(chiens_id)
        assert new_form_backup_count == form_backup_count + 2
        assert chien.syntactic_category == None
        assert chien.syntactic_category_string == u'?'
        assert chiens.syntactic_category_string == u'?-?'
        assert json.loads(chiens.morpheme_break_ids)[0][0][0][2] == None
