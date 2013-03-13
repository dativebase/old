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
import codecs
import simplejson as json
from time import sleep
from nose.tools import nottest
from paste.deploy import appconfig
from sqlalchemy.sql import desc
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Phonology
from onlinelinguisticdatabase.lib.bibtex import entryTypes

log = logging.getLogger(__name__)


class TestPhonologiesController(TestController):

    here = appconfig('config:test.ini', relative_to='.')['here']
    researchersPath = os.path.join(here, 'files', 'researchers')
    phonologyPath = os.path.join(here, 'analysis', 'phonology')
    testPhonologyScriptPath = os.path.join(here, 'onlinelinguisticdatabase',
                                    'tests', 'data', 'test_phonology.script')
    testPhonologyScript = h.normalize(
        codecs.open(testPhonologyScriptPath, 'r', 'utf8').read())

    testMalformedPhonologyScriptPath = os.path.join(here, 'onlinelinguisticdatabase',
                                    'tests', 'data', 'test_phonology_malformed.script')
    testMalformedPhonologyScript = h.normalize(
        codecs.open(testMalformedPhonologyScriptPath, 'r', 'utf8').read())

    testPhonologyNoPhonologyScriptPath = os.path.join(here, 'onlinelinguisticdatabase',
                                    'tests', 'data', 'test_phonology_malformed.script')
    testPhonologyNoPhonologyScript = h.normalize(
        codecs.open(testPhonologyNoPhonologyScriptPath, 'r', 'utf8').read())

    testMediumPhonologyScriptPath = os.path.join(here, 'onlinelinguisticdatabase',
                                    'tests', 'data', 'test_phonology_medium.script')
    testMediumPhonologyScript = h.normalize(
        codecs.open(testMediumPhonologyScriptPath, 'r', 'utf8').read())

    testLargePhonologyScriptPath = os.path.join(here, 'onlinelinguisticdatabase',
                                    'tests', 'data', 'test_phonology_large.script')
    testLargePhonologyScript = h.normalize(
        codecs.open(testLargePhonologyScriptPath, 'r', 'utf8').read())

    createParams = {
        'name': u'',
        'description': u'',
        'script': u''
    }

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language; recreate the phonologies.
    def tearDown(self):
        h.clearAllModels()
        h.destroyAllResearcherDirectories()
        h.destroyAllPhonologyDirectories()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

    #@nottest
    def test_index(self):
        """Tests that GET /phonologies returns an array of all phonologies and that orderBy and pagination parameters work correctly."""

        # Add 100 phonologies.
        def createPhonologyFromIndex(index):
            phonology = model.Phonology()
            phonology.name = u'Phonology %d' % index
            phonology.description = u'A phonology with %d rules' % index
            phonology.script = u'# After this comment, the script will begin.\n\n'
            return phonology
        phonologies = [createPhonologyFromIndex(i) for i in range(1, 101)]
        Session.add_all(phonologies)
        Session.commit()
        phonologies = h.getPhonologies(True)
        phonologiesCount = len(phonologies)

        # Test that GET /phonologies gives us all of the phonologies.
        response = self.app.get(url('phonologies'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == phonologiesCount
        assert resp[0]['name'] == u'Phonology 1'
        assert resp[0]['id'] == phonologies[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == phonologies[46].name
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Phonology', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('phonologies'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        resultSet = sorted(phonologies, key=lambda p: p.name, reverse=True)
        assert [p.id for p in resultSet] == [p['id'] for p in resp]
        assert response.content_type == 'application/json'

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Phonology', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('phonologies'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resultSet[46].name == resp['items'][0]['name']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Phonology', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('phonologies'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Phonologyist', 'orderByAttribute': 'nominal',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('phonologies'), orderByParams,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == phonologies[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    #@nottest
    def test_create(self):
        """Tests that POST /phonologies creates a new phonology
        or returns an appropriate error if the input is invalid.
        """

        # Attempt to create a phonology as a viewer and expect to fail
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Create a valid one
        originalPhonologyCount = Session.query(Phonology).count()
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newPhonologyCount = Session.query(Phonology).count()
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        assert newPhonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert 'phonology_%d.script' % resp['id'] in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testPhonologyScript

        # Invalid because name is not unique
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'The submitted value for Phonology.name is not unique.'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.createParams.copy()
        params.update({
            'name': u'',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.createParams.copy()
        params.update({
            'name': None,
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name is too long.
        params = self.createParams.copy()
        params.update({
            'name': 'Phonology' * 200,
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    #@nottest
    def test_new(self):
        """Tests that GET /phonologies/new returns an empty JSON object."""
        response = self.app.get(url('new_phonology'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /phonologies/id updates the phonology with id=id."""

        # Create a phonology to update.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Update the phonology
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.  Best yet!',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonologyId), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeModified = resp['datetimeModified']
        newPhonologyCount = Session.query(Phonology).count()
        assert phonologyCount == newPhonologyCount
        assert datetimeModified != originalDatetimeModified
        assert resp['description'] == u'Covers a lot of the data.  Best yet!'
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetimeModified for the update
        response = self.app.put(url('phonology', id=phonologyId), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonologyCount = newPhonologyCount
        newPhonologyCount = Session.query(Phonology).count()
        ourPhonologyDatetimeModified = Session.query(Phonology).get(phonologyId).datetimeModified
        assert ourPhonologyDatetimeModified.isoformat() == datetimeModified
        assert phonologyCount == newPhonologyCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /phonologies/id deletes the phonology with id=id."""

        # Create a phonology to delete.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert 'phonology_%d.script' % resp['id'] in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testPhonologyScript

        # Now delete the phonology
        response = self.app.delete(url('phonology', id=phonologyId), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        newPhonologyCount = Session.query(Phonology).count()
        assert newPhonologyCount == phonologyCount - 1
        assert resp['id'] == phonologyId
        assert response.content_type == 'application/json'
        assert not os.path.exists(phonologyDir)
        assert resp['script'] == self.testPhonologyScript

        # Trying to get the deleted phonology from the db should return None
        deletedPhonology = Session.query(Phonology).get(phonologyId)
        assert deletedPhonology == None

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('phonology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no phonology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('phonology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_show(self):
        """Tests that GET /phonologies/id returns the phonology with id=id or an appropriate error."""

        # Create a phonology to show.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Try to get a phonology using an invalid id
        id = 100000000000
        response = self.app.get(url('phonology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no phonology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('phonology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('phonology', id=phonologyId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert resp['script'] == u'# The rules will begin after this comment.\n\n'
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /phonologies/id/edit returns a JSON object of data necessary to edit the phonology with id=id.

        The JSON object is of the form {'phonology': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a phonology to edit.
        originalPhonologyCount = Session.query(Phonology).count()
        params = self.createParams.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyCount = Session.query(Phonology).count()
        phonologyId = resp['id']
        originalDatetimeModified = resp['datetimeModified']
        assert phonologyCount == originalPhonologyCount + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_phonology', id=phonologyId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_phonology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no phonology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_phonology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_phonology', id=phonologyId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['phonology']['name'] == u'Phonology'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'

    #@nottest
    def test_compile(self):
        """Tests that PUT /phonologies/compile/id compiles the foma script of the phonology with id.

        .. note::
        
            Phonology compilation is accomplished via a worker thread and
            requests to /phonologies/compile/id return immediately.  When the
            script compilation attempt has terminated, the values of the
            ``datetimeCompiled``, ``datetimeModified``, ``compileSucceeded``,
            ``compileMessage`` and ``modifier`` attributes of the phonology are
            updated.  Therefore, the tests must poll ``GET /phonologies/id``
            in order to know when the compilation-tasked worker has finished.

        .. note::
        
            Depending on system resources, the following tests may fail.  A fast
            system may compile the large FST in under 30 seconds; a slow one may
            fail to compile the medium one in under 30.

        Test for Modifier
        Backups

        """

        # Create a phonology with the test phonology script
        params = self.createParams.copy()
        params.update({
            'name': u'Blackfoot Phonology',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology1Id = resp['id']
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % phonology1Id)
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyBinaryFilename = 'phonology_%d.foma' % phonology1Id
        assert resp['name'] == u'Blackfoot Phonology'
        assert 'phonology_%d.script' % phonology1Id in phonologyDirContents
        assert 'phonology_%d.sh' % phonology1Id in phonologyDirContents
        assert phonologyBinaryFilename not in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testPhonologyScript
        assert resp['modifier']['role'] == u'administrator'

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology1Id),
                                headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']

        # Poll ``GET /phonologies/phonology1Id`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1Id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1Id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1Id)
            sleep(1)

        assert resp['compileSucceeded'] == True
        assert resp['compileMessage'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonologyBinaryFilename in os.listdir(phonologyDir)
        assert resp['modifier']['role'] == u'contributor'

        ########################################################################
        # Three types of scripts that won't compile
        ########################################################################

        # 1. Create a phonology whose script is malformed using
        # ``tests/data/test_phonology_malformed.script``.
        params = self.createParams.copy()
        params.update({
            'name': u'Blackfoot Phonology 2',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.testMalformedPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyId = resp['id']
        phonologyBinaryFilename = 'phonology_%d.foma' % phonologyId
        assert resp['name'] == u'Blackfoot Phonology 2'
        assert 'phonology_%d.script' % phonologyId in phonologyDirContents
        assert 'phonology_%d.sh' % phonologyId in phonologyDirContents
        assert phonologyBinaryFilename not in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testMalformedPhonologyScript

        # Attempt to compile the malformed phonology's script and expect to fail
        response = self.app.put(url(controller='phonologies', action='compile', id=phonologyId),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']
        assert resp['id'] == phonologyId

        # Poll ``GET /phonologies/phonologyId`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonologyId),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonologyId)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonologyId)
            sleep(1)

        assert resp['compileSucceeded'] == False
        assert resp['compileMessage'] == u'Phonology script is not well-formed; maybe no "phonology" FST was defined (?).'
        assert phonologyBinaryFilename not in os.listdir(phonologyDir)

        # 2. Create a phonology whose script does not define a regex called "phonology"
        # using ``tests/data/test_phonology_no_phonology.script``.
        params = self.createParams.copy()
        params.update({
            'name': u'Blackfoot Phonology 3',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.testPhonologyNoPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyId = resp['id']
        phonologyBinaryFilename = 'phonology_%d.foma' % phonologyId
        assert resp['name'] == u'Blackfoot Phonology 3'
        assert 'phonology_%d.script' % phonologyId in phonologyDirContents
        assert 'phonology_%d.sh' % phonologyId in phonologyDirContents
        assert phonologyBinaryFilename not in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testPhonologyNoPhonologyScript

        # Attempt to compile the malformed phonology's script and expect to fail
        response = self.app.put(url(controller='phonologies', action='compile', id=phonologyId),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']
        assert resp['id'] == phonologyId

        # Poll ``GET /phonologies/phonologyId`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonologyId),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonologyId)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonologyId)
            sleep(1)

        assert resp['compileSucceeded'] == False
        assert resp['compileMessage'] == u'Phonology script is not well-formed; maybe no "phonology" FST was defined (?).'
        assert phonologyBinaryFilename not in os.listdir(phonologyDir)

        # 3. Create a phonology whose script is empty.
        params = self.createParams.copy()
        params.update({
            'name': u'Blackfoot Phonology 4',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': u''
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyId = resp['id']
        phonologyBinaryFilename = 'phonology_%d.foma' % phonologyId
        assert resp['name'] == u'Blackfoot Phonology 4'
        assert 'phonology_%d.script' % phonologyId in phonologyDirContents
        assert 'phonology_%d.sh' % phonologyId in phonologyDirContents
        assert phonologyBinaryFilename not in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == u''

        # Attempt to compile the malformed phonology's script and expect to fail
        response = self.app.put(url(controller='phonologies', action='compile', id=phonologyId),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']
        assert resp['id'] == phonologyId

        # Poll ``GET /phonologies/phonologyId`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonologyId),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonologyId)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonologyId)
            sleep(1)

        assert resp['compileSucceeded'] == False
        assert resp['compileMessage'] == u'Phonology script is not well-formed; maybe no "phonology" FST was defined (?).'
        assert phonologyBinaryFilename not in os.listdir(phonologyDir)

        ########################################################################
        # Compile a medium phonology -- compilation should be long but not exceed the 30s limit.
        ########################################################################
        
        params = self.createParams.copy()
        params.update({
            'name': u'Blackfoot Phonology 5',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.testMediumPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyId = resp['id']
        phonologyBinaryFilename = 'phonology_%d.foma' % phonologyId
        assert resp['name'] == u'Blackfoot Phonology 5'
        assert 'phonology_%d.script' % phonologyId in phonologyDirContents
        assert 'phonology_%d.sh' % phonologyId in phonologyDirContents
        assert phonologyBinaryFilename not in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testMediumPhonologyScript

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonologyId),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']
        assert resp['id'] == phonologyId

        # Poll ``GET /phonologies/phonologyId`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonologyId),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonologyId)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonologyId)
            sleep(3)

        assert resp['compileSucceeded'] == True
        assert resp['compileMessage'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonologyBinaryFilename in os.listdir(phonologyDir)

        ########################################################################
        # Compile a large phonology -- compilation should exceed the 30s limit.
        ########################################################################
        
        params = self.createParams.copy()
        params.update({
            'name': u'Blackfoot Phonology 6',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.testLargePhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % resp['id'])
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyId = resp['id']
        phonologyBinaryFilename = 'phonology_%d.foma' % phonologyId
        assert resp['name'] == u'Blackfoot Phonology 6'
        assert 'phonology_%d.script' % phonologyId in phonologyDirContents
        assert 'phonology_%d.sh' % phonologyId in phonologyDirContents
        assert phonologyBinaryFilename not in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testLargePhonologyScript

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonologyId),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']
        assert resp['id'] == phonologyId

        # Poll ``GET /phonologies/phonologyId`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonologyId),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonologyId)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonologyId)
            sleep(3)

        assert resp['compileSucceeded'] == False
        assert resp['compileMessage'] == u'Phonology script is not well-formed; maybe no "phonology" FST was defined (?).'
        assert phonologyBinaryFilename not in os.listdir(phonologyDir)


        # Compile the first phonology's script again
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology1Id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        phonologyBinaryFilename = 'phonology_%d.foma' % phonology1Id
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % phonology1Id)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']

        # Poll ``GET /phonologies/phonology1Id`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1Id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1Id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1Id)
            sleep(1)

        assert resp['compileSucceeded'] == True
        assert resp['compileMessage'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonologyBinaryFilename in os.listdir(phonologyDir)

    #@nottest
    def test_applydown(self):

        # Create a phonology with the test phonology script
        params = self.createParams.copy()
        params.update({
            'name': u'Blackfoot Phonology',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.testPhonologyScript
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology1Id = resp['id']
        phonologyDir = os.path.join(self.phonologyPath, 'phonology_%d' % phonology1Id)
        phonologyDirContents = os.listdir(phonologyDir)
        phonologyBinaryFilename = 'phonology_%d.foma' % phonology1Id
        assert resp['name'] == u'Blackfoot Phonology'
        assert 'phonology_%d.script' % phonology1Id in phonologyDirContents
        assert 'phonology_%d.sh' % phonology1Id in phonologyDirContents
        assert phonologyBinaryFilename not in phonologyDirContents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.testPhonologyScript
        assert resp['modifier']['role'] == u'administrator'

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology1Id),
                                headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        datetimeCompiled = resp['datetimeCompiled']
        compileSucceeded = resp['compileSucceeded']
        compileMessage = resp['compileMessage']

        # Poll ``GET /phonologies/phonology1Id`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1Id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1Id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1Id)
            sleep(1)

        assert resp['compileSucceeded'] == True
        assert resp['compileMessage'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonologyBinaryFilename in os.listdir(phonologyDir)
        assert resp['modifier']['role'] == u'contributor'


        params = json.dumps([u'nit-wa', 'kit-ihpiyi'])
        response = self.app.put(url(controller='phonologies', action='applydown', id=phonology1Id),
                                params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        log.debug(resp)