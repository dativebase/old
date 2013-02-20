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
from onlinelinguisticdatabase.model import SyntacticCategory
from onlinelinguisticdatabase.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


################################################################################
# Functions for creating & retrieving test data
################################################################################

class TestSyntacticcategoriesController(TestController):

    createFormParams = {
        'transcription': u'',
        'phoneticTranscription': u'',
        'narrowPhoneticTranscription': u'',
        'morphemeBreak': u'',
        'grammaticality': u'',
        'morphemeGloss': u'',
        'glosses': [],
        'comments': u'',
        'speakerComments': u'',
        'elicitationMethod': u'',
        'tags': [],
        'syntacticCategory': u'',
        'speaker': u'',
        'elicitor': u'',
        'verifier': u'',
        'source': u'',
        'status': u'tested',
        'dateElicited': u''     # mm/dd/yyyy
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

    #@nottest
    def test_index(self):
        """Tests that GET /syntacticcategories returns an array of all syntactic categories and that orderBy and pagination parameters work correctly."""

        # Add 100 syntactic categories.
        def createSyntacticCategoryFromIndex(index):
            syntacticCategory = model.SyntacticCategory()
            syntacticCategory.name = u'sc%d' % index
            syntacticCategory.type = u'lexical'
            syntacticCategory.description = u'description %d' % index
            return syntacticCategory
        syntacticCategories = [createSyntacticCategoryFromIndex(i) for i in range(1, 101)]
        Session.add_all(syntacticCategories)
        Session.commit()
        syntacticCategories = h.getSyntacticCategories(True)
        syntacticCategoriesCount = len(syntacticCategories)

        # Test that GET /syntacticcategories gives us all of the syntactic categories.
        response = self.app.get(url('syntacticcategories'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == syntacticCategoriesCount
        assert resp[0]['name'] == u'sc1'
        assert resp[0]['id'] == syntacticCategories[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('syntacticcategories'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == syntacticCategories[46].name
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'SyntacticCategory', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('syntacticcategories'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted([sc.name for sc in syntacticCategories], reverse=True)
        assert resultSet == [sc['name'] for sc in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'SyntacticCategory', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('syntacticcategories'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['name']
        assert response.content_type == 'application/json'

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'SyntacticCategory', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('syntacticcategories'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'SyntacticCategoryist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('syntacticcategories'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == syntacticCategories[0].id
        assert response.content_type == 'application/json'

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('syntacticcategories'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('syntacticcategories'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    #@nottest
    def test_create(self):
        """Tests that POST /syntacticcategories creates a new syntactic category
        or returns an appropriate error if the input is invalid.
        """

        originalSCCount = Session.query(SyntacticCategory).count()

        # Create a valid one
        params = json.dumps({'name': u'sc', 'type': u'lexical', 'description': u'Described.'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newSCCount = Session.query(SyntacticCategory).count()
        assert newSCCount == originalSCCount + 1
        assert resp['name'] == u'sc'
        assert resp['description'] == u'Described.'
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

        # Invalid because type is not in utils.syntacticCategoryTypes
        params = json.dumps({'name': u'name' * 400, 'type': u'spatial', 'description': u'Described.'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['type'] == u"Value must be one of: lexical; phrasal; sentential (not u'spatial')"
        assert response.content_type == 'application/json'

    #@nottest
    def test_new(self):
        """Tests that GET /syntacticcategories/new returns an empty JSON object."""
        response = self.app.get(url('new_syntacticcategory'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['syntacticCategoryTypes'] == list(h.syntacticCategoryTypes)
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /syntacticcategories/id updates the syntacticcategory with id=id."""

        # Create an syntactic category to update.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntacticCategoryCount = Session.query(SyntacticCategory).count()
        syntacticCategoryId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Update the syntactic category
        sleep(1)    # sleep for a second to ensure that MySQL registers a different datetimeModified for the update
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'More content-ful description.'})
        response = self.app.put(url('syntacticcategory', id=syntacticCategoryId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newSyntacticCategoryCount = Session.query(SyntacticCategory).count()
        assert syntacticCategoryCount == newSyntacticCategoryCount
        assert datetimeModified != originalDatetimeModified
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('syntacticcategory', id=syntacticCategoryId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        syntacticCategoryCount = newSyntacticCategoryCount
        newSyntacticCategoryCount = Session.query(SyntacticCategory).count()
        ourSCDatetimeModified = Session.query(SyntacticCategory).get(syntacticCategoryId).datetimeModified
        assert ourSCDatetimeModified.isoformat() == datetimeModified
        assert syntacticCategoryCount == newSyntacticCategoryCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /syntacticcategories/id deletes the syntacticCategory with id=id."""

        # Create an syntactic category to delete.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntacticCategoryCount = Session.query(SyntacticCategory).count()
        syntacticCategoryId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Now delete the syntactic category
        response = self.app.delete(url('syntacticcategory', id=syntacticCategoryId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newSyntacticCategoryCount = Session.query(SyntacticCategory).count()
        assert newSyntacticCategoryCount == syntacticCategoryCount - 1
        assert resp['id'] == syntacticCategoryId
        assert response.content_type == 'application/json'

        # Trying to get the deleted syntactic category from the db should return None
        deletedSyntacticCategory = Session.query(SyntacticCategory).get(syntacticCategoryId)
        assert deletedSyntacticCategory == None

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

    #@nottest
    def test_show(self):
        """Tests that GET /syntacticcategories/id returns the syntactic category with id=id or an appropriate error."""

        # Create an syntactic category to show.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntacticCategoryCount = Session.query(SyntacticCategory).count()
        syntacticCategoryId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Try to get a syntacticCategory using an invalid id
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
        response = self.app.get(url('syntacticcategory', id=syntacticCategoryId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'name'
        assert resp['description'] == u'description'
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /syntacticcategories/id/edit returns a JSON object of data necessary to edit the syntactic category with id=id.

        The JSON object is of the form {'syntacticCategory': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create an syntactic category to edit.
        params = json.dumps({'name': u'name', 'type': u'lexical', 'description': u'description'})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        syntacticCategoryCount = Session.query(SyntacticCategory).count()
        syntacticCategoryId = resp['id']
        originalDatetimeModified = resp['datetimeModified']

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_syntacticcategory', id=syntacticCategoryId), status=401)
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
        response = self.app.get(url('edit_syntacticcategory', id=syntacticCategoryId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['syntacticCategory']['name'] == u'name'
        assert resp['data']['syntacticCategoryTypes'] == list(h.syntacticCategoryTypes)
        assert response.content_type == 'application/json'


    #@nottest
    def test_category_percolation(self):
        """Tests that changes to a category's name and deletion of a category trigger updates to forms containing morphemes of that category.
        """

        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add(applicationSettings)
        Session.commit()

        extra_environ = {'test.authentication.role': u'administrator',
                               'test.applicationSettings': True}

        # Create an N category
        params = json.dumps({'name': u'N', 'type': u'lexical', 'description': u''})
        response = self.app.post(url('syntacticcategories'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        NId = resp['id']
        assert resp['name'] == u'N'
        assert response.content_type == 'application/json'

        # Create a lexical form 'chien/dog' of category N
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'chien',
            'morphemeBreak': u'chien',
            'morphemeGloss': u'dog',
            'glosses': [{'gloss': u'dog', 'glossGrammaticality': u''}],
            'syntacticCategory': NId
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, extra_environ)
        resp = json.loads(response.body)
        chienId = resp['id']
        assert resp['morphemeBreakIDs'][0][0][0][1] == u'dog'
        assert resp['morphemeBreakIDs'][0][0][0][2] == u'N'
        assert resp['morphemeGlossIDs'][0][0][0][1] == u'chien'
        assert resp['morphemeGlossIDs'][0][0][0][2] == u'N'
        assert resp['syntacticCategoryString'] == u'N'
        assert resp['breakGlossCategory'] == u'chien|dog|N'

        # Create a phrasal form 'chien-s/dog-PL' that will contain 'chien/dog'
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'chiens',
            'morphemeBreak': u'chien-s',
            'morphemeGloss': u'dog-PL',
            'glosses': [{'gloss': u'dogs', 'glossGrammaticality': u''}],
            'syntacticCategory': NId
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers, extra_environ)
        resp = json.loads(response.body)
        chiensId = resp['id']
        assert resp['morphemeBreakIDs'][0][0][0][1] == u'dog'
        assert resp['morphemeBreakIDs'][0][0][0][2] == u'N'
        assert resp['morphemeGlossIDs'][0][0][0][1] == u'chien'
        assert resp['morphemeGlossIDs'][0][0][0][2] == u'N'
        assert resp['syntacticCategoryString'] == u'N-?'
        assert resp['breakGlossCategory'] == u'chien|dog|N-s|PL|?'

        # Now update the name of the N category and expect that change to cause
        # an update to the chien/dog and chien-s/dog-PL forms.
        formBackupCount = Session.query(model.FormBackup).count()
        params = json.dumps({'name': u'Noun', 'type': u'lexical', 'description': u''})
        response = self.app.put(url('syntacticcategory', id=NId), params, self.json_headers, extra_environ)
        newFormBackupCount = Session.query(model.FormBackup).count()
        chien = Session.query(model.Form).get(chienId)
        chiens = Session.query(model.Form).get(chiensId)
        assert newFormBackupCount == formBackupCount + 2
        assert chien.syntacticCategoryString == u'Noun'
        assert chiens.syntacticCategoryString == u'Noun-?'
        assert json.loads(chiens.morphemeBreakIDs)[0][0][0][2] == u'Noun'

        # Now update something besides the name attribute of the N/Noun category
        # and expect no updates to any forms.
        params = json.dumps({'name': u'Noun', 'type': u'lexical', 'description': u'Blah!'})
        response = self.app.put(url('syntacticcategory', id=NId), params, self.json_headers, extra_environ)
        formBackupCount = newFormBackupCount
        newFormBackupCount = Session.query(model.FormBackup).count()
        chien = chiens = None
        chien = Session.query(model.Form).get(chienId)
        chiens = Session.query(model.Form).get(chiensId)
        assert newFormBackupCount == formBackupCount
        assert chien.syntacticCategoryString == u'Noun'
        assert chiens.syntacticCategoryString == u'Noun-?'
        assert json.loads(chiens.morphemeBreakIDs)[0][0][0][2] == u'Noun'

        # Test deletion of sc
        response = self.app.delete(url('syntacticcategory', id=NId), headers=self.json_headers,
                                   extra_environ=extra_environ)
        formBackupCount = newFormBackupCount
        newFormBackupCount = Session.query(model.FormBackup).count()
        chien = chiens = None
        chien = Session.query(model.Form).get(chienId)
        chiens = Session.query(model.Form).get(chiensId)
        assert newFormBackupCount == formBackupCount + 2
        assert chien.syntacticCategory == None
        assert chien.syntacticCategoryString == u'?'
        assert chiens.syntacticCategoryString == u'?-?'
        assert json.loads(chiens.morphemeBreakIDs)[0][0][0][2] == None
