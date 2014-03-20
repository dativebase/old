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
import os
import codecs
import simplejson as json
from uuid import uuid4
from time import sleep
from nose.tools import nottest
from sqlalchemy.sql import desc
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Phonology, PhonologyBackup

log = logging.getLogger(__name__)

class TestPhonologiesController(TestController):

    def __init__(self, *args, **kwargs):
        TestController.__init__(self, *args, **kwargs)
        self.test_phonology_script = h.normalize(
            codecs.open(self.test_phonology_script_path, 'r', 'utf8').read())
        self.test_malformed_phonology_script = h.normalize(
            codecs.open(self.test_malformed_phonology_script_path, 'r', 'utf8').read())
        self.test_phonology_no_phonology_script = h.normalize(
            codecs.open(self.test_phonology_no_phonology_script_path, 'r', 'utf8').read())
        self.test_medium_phonology_script = h.normalize(
            codecs.open(self.test_medium_phonology_script_path, 'r', 'utf8').read())
        self.test_large_phonology_script = h.normalize(
            codecs.open(self.test_large_phonology_script_path, 'r', 'utf8').read())
        self.test_phonology_testless_script = h.normalize(
            codecs.open(self.test_phonology_testless_script_path, 'r', 'utf8').read())

    # Clear all models in the database except Language; recreate the phonologies.
    def tearDown(self):
        TestController.tearDown(self, del_global_app_set=True,
                dirs_to_destroy=['user', 'phonology'])

    @nottest
    def test_index(self):
        """Tests that GET /phonologies returns an array of all phonologies and that order_by and pagination parameters work correctly."""

        # Add 100 phonologies.
        def create_phonology_from_index(index, parent, boundary):
            phonology = model.Phonology(parent, boundary=boundary)
            phonology.name = u'Phonology %d' % index
            phonology.description = u'A phonology with %d rules' % index
            phonology.script = u'# After this comment, the script will begin.\n\n'
            return phonology
        phonologies_path = self.phonologies_path
        boundary = h.word_boundary_symbol
        phonologies = [create_phonology_from_index(i, phonologies_path, boundary)
                for i in range(1, 101)]
        Session.add_all(phonologies)
        Session.commit()
        phonologies = h.get_phonologies(True)
        phonologies_count = len(phonologies)

        # Test that GET /phonologies gives us all of the phonologies.
        response = self.app.get(url('phonologies'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == phonologies_count
        assert resp[0]['name'] == u'Phonology 1'
        assert resp[0]['id'] == phonologies[0].id
        assert response.content_type == 'application/json'

        # Test the paginator GET params.
        paginator = {'items_per_page': 23, 'page': 3}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == phonologies[46].name
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'Phonology', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('phonologies'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        result_set = sorted(phonologies, key=lambda p: p.name, reverse=True)
        assert [p.id for p in result_set] == [p['id'] for p in resp]
        assert response.content_type == 'application/json'

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'Phonology', 'order_by_attribute': 'name',
                     'order_by_direction': 'desc', 'items_per_page': 23, 'page': 3}
        response = self.app.get(url('phonologies'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert result_set[46].name == resp['items'][0]['name']

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'Phonology', 'order_by_attribute': 'name',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('phonologies'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

        # Expect the default BY id ASCENDING ordering when the order_by_model/Attribute
        # param is invalid.
        order_by_params = {'order_by_model': 'Phonologyist', 'order_by_attribute': 'nominal',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('phonologies'), order_by_params,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == phonologies[0].id

        # Expect a 400 error when the paginator GET params are empty
        # or are integers less than 1
        paginator = {'items_per_page': u'a', 'page': u''}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        paginator = {'items_per_page': 0, 'page': -1}
        response = self.app.get(url('phonologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /phonologies creates a new phonology
        or returns an appropriate error if the input is invalid.
        """

        # Attempt to create a phonology as a viewer and expect to fail
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': self.test_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_view, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Create a valid one
        original_phonology_count = Session.query(Phonology).count()
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_phonology_count = Session.query(Phonology).count()
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % resp['id'])
        phonology_dir_contents = os.listdir(phonology_dir)
        assert new_phonology_count == original_phonology_count + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert 'phonology.script' in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_phonology_script

        # Invalid because name is not unique
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonology_count = new_phonology_count
        new_phonology_count = Session.query(Phonology).count()
        assert new_phonology_count == phonology_count
        assert resp['errors']['name'] == u'The submitted value for Phonology.name is not unique.'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonology_count = new_phonology_count
        new_phonology_count = Session.query(Phonology).count()
        assert new_phonology_count == phonology_count
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name must be a non-empty string
        params = self.phonology_create_params.copy()
        params.update({
            'name': None,
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonology_count = new_phonology_count
        new_phonology_count = Session.query(Phonology).count()
        assert new_phonology_count == phonology_count
        assert resp['errors']['name'] == u'Please enter a value'
        assert response.content_type == 'application/json'

        # Invalid because name is too long.
        params = self.phonology_create_params.copy()
        params.update({
            'name': 'Phonology' * 200,
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonology_count = new_phonology_count
        new_phonology_count = Session.query(Phonology).count()
        assert new_phonology_count == phonology_count
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert response.content_type == 'application/json'

    @nottest
    def test_new(self):
        """Tests that GET /phonologies/new returns an empty JSON object."""
        response = self.app.get(url('new_phonology'), headers=self.json_headers,
                                extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == {}
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /phonologies/id updates the phonology with id=id."""

        # Create a phonology to update.
        original_phonology_count = Session.query(Phonology).count()
        params = self.phonology_create_params.copy()
        original_script = u'# The rules will begin after this comment.\n\n'
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': original_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_count = Session.query(Phonology).count()
        phonology_id = resp['id']
        original_datetime_modified = resp['datetime_modified']
        assert phonology_count == original_phonology_count + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Update the phonology
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        new_script = u'define phonology o -> 0 || t "-" _ k "-";'
        orig_backup_count = Session.query(PhonologyBackup).count()
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.  Best yet!',
            'script': new_script
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonology_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        new_backup_count = Session.query(PhonologyBackup).count()
        datetime_modified = resp['datetime_modified']
        new_phonology_count = Session.query(Phonology).count()
        assert phonology_count == new_phonology_count
        assert datetime_modified != original_datetime_modified
        assert resp['description'] == u'Covers a lot of the data.  Best yet!'
        assert resp['script'] == new_script
        assert response.content_type == 'application/json'
        assert orig_backup_count + 1 == new_backup_count
        backup = Session.query(PhonologyBackup).filter(
            PhonologyBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(PhonologyBackup.id)).first()
        assert backup.datetime_modified.isoformat() == original_datetime_modified
        assert backup.script == original_script
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        response = self.app.put(url('phonology', id=phonology_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        phonology_count = new_phonology_count
        new_phonology_count = Session.query(Phonology).count()
        our_phonology_datetime_modified = Session.query(Phonology).get(phonology_id).datetime_modified
        assert our_phonology_datetime_modified.isoformat() == datetime_modified
        assert phonology_count == new_phonology_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    @nottest
    def test_delete(self):
        """Tests that DELETE /phonologies/id deletes the phonology with id=id."""

        # Count the original number of phonologies and phonology_backups.
        phonology_count = Session.query(Phonology).count()
        phonology_backup_count = Session.query(PhonologyBackup).count()

        # Create a phonology to delete.
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': self.test_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_id = resp['id']
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % resp['id'])
        phonology_dir_contents = os.listdir(phonology_dir)
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert 'phonology.script' in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_phonology_script

        # Now count the phonologies and phonology_backups.
        new_phonology_count = Session.query(Phonology).count()
        new_phonology_backup_count = Session.query(PhonologyBackup).count()
        assert new_phonology_count == phonology_count + 1
        assert new_phonology_backup_count == phonology_backup_count

        # Now delete the phonology
        response = self.app.delete(url('phonology', id=phonology_id), headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_count = new_phonology_count
        new_phonology_count = Session.query(Phonology).count()
        phonology_backup_count = new_phonology_backup_count
        new_phonology_backup_count = Session.query(PhonologyBackup).count()
        assert new_phonology_count == phonology_count - 1
        assert new_phonology_backup_count == phonology_backup_count + 1
        assert resp['id'] == phonology_id
        assert response.content_type == 'application/json'
        assert not os.path.exists(phonology_dir)
        assert resp['script'] == self.test_phonology_script

        # Trying to get the deleted phonology from the db should return None
        deleted_phonology = Session.query(Phonology).get(phonology_id)
        assert deleted_phonology == None

        # The backed up phonology should have the deleted phonology's attributes
        backed_up_phonology = Session.query(PhonologyBackup).filter(
            PhonologyBackup.UUID==unicode(resp['UUID'])).first()
        assert backed_up_phonology.name == resp['name']
        modifier = json.loads(unicode(backed_up_phonology.modifier))
        assert modifier['first_name'] == u'Admin'
        assert backed_up_phonology.datetime_entered.isoformat() == resp['datetime_entered']
        assert backed_up_phonology.UUID == resp['UUID']

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

    @nottest
    def test_show(self):
        """Tests that GET /phonologies/id returns the phonology with id=id or an appropriate error."""

        # Create a phonology to show.
        original_phonology_count = Session.query(Phonology).count()
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_count = Session.query(Phonology).count()
        phonology_id = resp['id']
        assert phonology_count == original_phonology_count + 1
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
        response = self.app.get(url('phonology', id=phonology_id), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'
        assert resp['script'] == u'# The rules will begin after this comment.\n\n'
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /phonologies/id/edit returns a JSON object of data necessary to edit the phonology with id=id.

        The JSON object is of the form {'phonology': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Create a phonology to edit.
        original_phonology_count = Session.query(Phonology).count()
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': u'# The rules will begin after this comment.\n\n'
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_count = Session.query(Phonology).count()
        phonology_id = resp['id']
        assert phonology_count == original_phonology_count + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_phonology', id=phonology_id), status=401)
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
        response = self.app.get(url('edit_phonology', id=phonology_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['phonology']['name'] == u'Phonology'
        assert resp['data'] == {}
        assert response.content_type == 'application/json'

    @nottest
    def test_compile(self):
        """Tests that PUT /phonologies/id/compile compiles the foma script of the phonology with id.

        .. note::

            Phonology compilation is accomplished via a worker thread and
            requests to /phonologies/id/compile return immediately.  When the
            script compilation attempt has terminated, the values of the
            ``compile_attempt``, ``datetime_modified``, ``compile_succeeded``,
            ``compile_message`` and ``modifier`` attributes of the phonology are
            updated.  Therefore, the tests must poll ``GET /phonologies/id``
            in order to know when the compilation-tasked worker has finished.

        .. note::

            Depending on system resources, the following tests may fail.  A fast
            system may compile the large FST in under 30 seconds; a slow one may
            fail to compile the medium one in under 30.

        Backups

        """
        # Create a phonology with the test phonology script
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology1_id = resp['id']
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % phonology1_id)
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_phonology_script
        assert resp['modifier']['role'] == u'administrator'

        # If foma is not installed, make sure the error message is being returned
        # and exit the test.
        if not h.foma_installed(force_check=True):
            response = self.app.put(url(controller='phonologies', action='compile',
                        id=phonology1_id), headers=self.json_headers,
                        extra_environ=self.extra_environ_contrib, status=400)
            resp = json.loads(response.body)
            assert resp['error'] == u'Foma and flookup are not installed.'
            return

        # Attempt to get the compiled script before it has been created.
        response = self.app.get(url(controller='phonologies', action='servecompiled',
            id=phonology1_id), headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'Phonology %d has not been compiled yet.' % phonology1_id

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile',
                    id=phonology1_id), headers=self.json_headers,
                    extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']
        compile_succeeded = resp['compile_succeeded']
        compile_message = resp['compile_message']

        # Poll ``GET /phonologies/phonology1_id`` until ``compile_attempt`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1_id)
            sleep(1)
        phonology_dir_contents = os.listdir(phonology_dir)
        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonology_binary_filename in phonology_dir_contents
        assert resp['modifier']['role'] == u'contributor'

        # Get the compiled foma script.
        response = self.app.get(url(controller='phonologies', action='servecompiled',
            id=phonology1_id), headers=self.json_headers, extra_environ=self.extra_environ_admin)
        phonology_binary_path = os.path.join(self.phonologies_path, 'phonology_%d' % phonology1_id,
               'phonology.foma')
        foma_file = open(phonology_binary_path, 'rb')
        foma_file_content = foma_file.read()
        assert foma_file_content == response.body
        assert response.content_type == u'application/octet-stream'

        # Attempt to get the comopiled foma script of a non-existent phonology.
        response = self.app.get(url(controller='phonologies', action='servecompiled',
            id=123456789), headers=self.json_headers,
            extra_environ=self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no phonology with id 123456789'

        ########################################################################
        # Three types of scripts that won't compile
        ########################################################################

        # 1. Create a phonology whose script is malformed using
        # ``tests/data/test_phonology_malformed.script``.
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology 2',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_malformed_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % resp['id'])
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_id = resp['id']
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology 2'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_malformed_phonology_script

        # Attempt to compile the malformed phonology's script and expect to fail
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']
        compile_succeeded = resp['compile_succeeded']
        compile_message = resp['compile_message']
        assert resp['id'] == phonology_id

        # Poll ``GET /phonologies/phonology_id`` until ``compile_attempt`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology_id)
            sleep(1)

        assert resp['compile_succeeded'] == False
        assert resp['compile_message'].startswith(u'Foma script is not a well-formed phonology')
        assert phonology_binary_filename not in os.listdir(phonology_dir)

        # 2. Create a phonology whose script does not define a regex called "phonology"
        # using ``tests/data/test_phonology_no_phonology.script``.
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology 3',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_phonology_no_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % resp['id'])
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_id = resp['id']
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology 3'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_phonology_no_phonology_script

        # Attempt to compile the malformed phonology's script and expect to fail
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        compile_attempt = resp['compile_attempt']
        compile_succeeded = resp['compile_succeeded']
        compile_message = resp['compile_message']
        assert resp['id'] == phonology_id

        # Poll ``GET /phonologies/phonology_id`` until ``compile_attempt`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology_id)
            sleep(1)

        assert resp['compile_succeeded'] == False
        assert resp['compile_message'].startswith(u'Foma script is not a well-formed phonology')
        assert phonology_binary_filename not in os.listdir(phonology_dir)

        # 3. Create a phonology whose script is empty.
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology 4',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': u''
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % resp['id'])
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_id = resp['id']
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology 4'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == u''

        # Attempt to compile the malformed phonology's script and expect to fail
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']
        compile_succeeded = resp['compile_succeeded']
        compile_message = resp['compile_message']
        assert resp['id'] == phonology_id

        # Poll ``GET /phonologies/phonology_id`` until ``compile_attempt`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology_id)
            sleep(1)

        assert resp['compile_succeeded'] == False
        assert resp['compile_message'].startswith(u'Foma script is not a well-formed phonology')
        assert phonology_binary_filename not in os.listdir(phonology_dir)

        ########################################################################
        # Compile a medium phonology -- compilation should be long but not exceed the 30s limit.
        ########################################################################
        
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology 5',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_medium_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % resp['id'])
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_id = resp['id']
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology 5'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_medium_phonology_script

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']
        compile_succeeded = resp['compile_succeeded']
        compile_message = resp['compile_message']
        assert resp['id'] == phonology_id

        # Poll ``GET /phonologies/phonology_id`` until ``compile_attempt`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology_id)
            sleep(3)

        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonology_binary_filename in os.listdir(phonology_dir)

        ########################################################################
        # Compile a large phonology -- compilation should exceed the 30s limit.
        ########################################################################

        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology 6',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_large_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % resp['id'])
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_id = resp['id']
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology 6'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_large_phonology_script

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']
        compile_succeeded = resp['compile_succeeded']
        compile_message = resp['compile_message']
        assert resp['id'] == phonology_id

        # Poll ``GET /phonologies/phonology_id`` until ``compile_attempt`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology_id)
            sleep(3)

        assert resp['compile_succeeded'] == False
        assert resp['compile_message'].startswith(u'Foma script is not a well-formed phonology')
        assert phonology_binary_filename not in os.listdir(phonology_dir)


        # Compile the first phonology's script again
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology1_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_binary_filename = 'phonology.foma'
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % phonology1_id)
        compile_attempt = resp['compile_attempt']

        # Poll ``GET /phonologies/phonology1_id`` until ``compile_attempt`` has
        # changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1_id)
            sleep(1)

        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonology_binary_filename in os.listdir(phonology_dir)

    @nottest
    def test_applydown(self):
        """Tests that ``GET /phonologies/id/applydown`` phonologizes input morpho-phonemic segmentations.

        """
        # Create a phonology with the test phonology script
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology1_id = resp['id']
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % phonology1_id)
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_phonology_script
        assert resp['modifier']['role'] == u'administrator'

        # If foma is not installed, make sure the error message is being returned
        # and exit the test.
        if not h.foma_installed(force_check=True):
            params = json.dumps({'transcriptions': u'nit-wa'})
            response = self.app.put(url(controller='phonologies',
                        action='applydown', id=phonology1_id), params,
                        self.json_headers, self.extra_environ_admin, status=400)
            resp = json.loads(response.body)
            assert resp['error'] == u'Foma and flookup are not installed.'
            return

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology1_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']

        # Poll ``GET /phonologies/phonology1_id`` until ``compile_attempt`` has changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1_id)
            sleep(1)

        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonology_binary_filename in os.listdir(phonology_dir)
        assert resp['modifier']['role'] == u'contributor'

        # Phonologize one morpho-phonemic segmentation.  Note that the value of
        # the ``transcriptions`` key can be a string (as here) or a list of strings.
        params = json.dumps({'transcriptions': u'nit-wa'})
        response = self.app.put(url(controller='phonologies', action='applydown',
                    id=phonology1_id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_dir_path = os.path.join(self.phonologies_path,
                                        'phonology_%d' % phonology1_id)
        phonology_dir_contents = os.listdir(phonology_dir_path)
        assert resp[u'nit-wa'] == [u'nita']
        # Make sure the temporary phonologization files have been deleted.
        assert not [fn for fn in phonology_dir_contents if fn[:7] == 'inputs_']
        assert not [fn for fn in phonology_dir_contents if fn[:8] == 'outputs_']
        assert not [fn for fn in phonology_dir_contents if fn[:10] == 'applydown_']

        # Repeat the above but use the synonym ``PUT /phonologies/id/phonologize``.
        params = json.dumps({'transcriptions': u'nit-wa'})
        response = self.app.put(url('/phonologies/%d/phonologize' % phonology1_id),
                                params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp[u'nit-wa'] == [u'nita']

        # Phonologize a large list of segmentations.  (These are the tests from
        # ``tests/data/test_phonology.script``.)
        tests = {
            u"nit-waanIt-k-wa": [u"nitaanikka"],
            u"nit-waanIt-aa-wa": [u"nitaanistaawa"],
            u"nit-siksipawa": [u"nitssiksipawa"],
            u"nit-ssiko\u0301pii": [u"nitsssiko\u0301pii"],
            u"a\u0301-si\u0301naaki-wa": [u"a\u0301i\u0301si\u0301naakiwa"],
            u"nika\u0301a\u0301-ssiko\u0301pii": [u"nika\u0301i\u0301ssiko\u0301pii"],
            u"ka\u0301ta\'-simi-wa": [u"ka\u0301tai\'simiwa"],
            u"a\u0301ak-oto-apinnii-wa": [u"a\u0301akotaapinniiwa",
                                          u"a\u0301akotapinniiwa"],
            u"w-i\u0301nni": [u"o\u0301nni"],
            u"w-iihsi\u0301ssi": [u"ohsi\u0301ssi"],
            u"a\u0301ak-Ipiima": [u"a\u0301aksipiima"],
            u"kitsi\u0301'powata-oaawa": [u"kitsi\u0301'powatawaawa"],
            u"a\u0301-Io'kaa-wa": [u"a\u0301yo'kaawa"],
            u"yaato\u0301o\u0301-t": [u"aato\u0301o\u0301t"],
            u"waani\u0301i\u0301-t": [u"aani\u0301i\u0301t"],
            u"w-o\u0301ko'si": [u"o\u0301ko'si"],
            u"a\u0301-yo'kaa-o'pa": [u"a\u0301yo'kao'pa"],
            u"imita\u0301a\u0301-iksi": [u"imita\u0301i\u0301ksi"],
            u"a\u0301-yo'kaa-yi-aawa": [u"a\u0301yo'kaayaawa"],
            u"a\u0301-ihpiyi-o'pa": [u"a\u0301i\u0301hpiyo'pa"],
            u"a\u0301-okstaki-yi-aawa": [u"a\u0301o\u0301kstakiiyaawa",
                                         u"a\u0301o\u0301kstakiyaawa"],
            u"a\u0301-okska'si-o'pa": [u"a\u0301o\u0301kska'so'pa"],
            u"nit-Ioyi": [u"nitsoyi"],
            u"otokska'si-hsi": [u"otokska'ssi"],
            u"ota\u0301'po'taki-hsi": [u"ota\u0301'po'takssi"],
            u"pii-hsini": [u"pissini"],
            u"a\u0301ak-yaatoowa": [u"a\u0301akaatoowa"],
            u"nit-waanii": [u"nitaanii"],
            u"kika\u0301ta'-waaniihpa": [u"kika\u0301ta'waaniihpa"],
            u"a\u0301i\u0301hpiyi-yina\u0301yi": [u"a\u0301i\u0301hpiiyina\u0301yi",
                                                  u"a\u0301i\u0301hpiyiyina\u0301yi"],
            u"a\u0301o\u0301kska'si-hpinnaan": [u"a\u0301o\u0301kska'sspinnaan"],
            u"nit-it-itsiniki": [u"nitsitsitsiniki"],
            u"a\u0301'-omai'taki-wa": [u"a\u0301o\u0301'mai'takiwa"],
            u"ka\u0301ta'-ookaawaatsi": [u"ka\u0301taookaawaatsi"],
            u"ka\u0301ta'-ottakiwaatsi": [u"ka\u0301taoottakiwaatsi"],
            u"a\u0301'-isttohkohpiy'ssi": [u"a\u0301i\u0301isttohkohpiy'ssi"],
            u"a\u0301'-o'tooyiniki": [u"a\u0301o\u0301'tooyiniki"],
            u"ka\u0301ta'-ohto'toowa": [u"ka\u0301tao'ohto'toowa",
                                        u"ka\u0301taohto'toowa"],
            u"nit-ssksinoawa": [u"nitssksinoawa"],
            u"a\u0301-okska'siwa": [u"a\u0301o\u0301kska'siwa"],
            u"atsiki\u0301-istsi": [u"atsiki\u0301i\u0301stsi"],
            u"kakko\u0301o\u0301-iksi": [u"kakko\u0301i\u0301ksi"],
            u"nit-ihpiyi": [u"nitsspiyi"],
            u"sa-oht-yi": [u"saohtsi"],
            u"nit-yo'kaa": [u"nitso'kaa"],
            u"nit-a\u0301ak-yo'kaa": [u"nita\u0301akso'kaa"],
            u"nit-a\u0301ak-ooyi": [u"nita\u0301aksoyi"],
            u"nit-ooyi": [u"nitsoyi"],
            u"ooyi": [u"iiyi"],
            u"nit-yooht-wa": [u"nitoohtowa"],
            u"nit-yooht-o-aa": [u"nitsi\u0301i\u0301yoohtoaa"],
            u"nit-ya\u0301api": [u"nitsaapi", u"nitsi\u0301aapi"]
        }

        params = json.dumps({'transcriptions': tests.keys()})
        response = self.app.put(url(controller='phonologies', action='applydown',
                                    id=phonology1_id),
                                params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert set(resp.keys()) == set(tests.keys())
        assert bool(set(resp[u'a\u0301ak-yaatoowa']) & set(tests[u'a\u0301ak-yaatoowa']))
        #for key in resp:
        #    was_anticipated = bool(set(resp[key]) & set(tests[key]))
        #    log.debug('%s => %s was anticipated: %s.' % (
        #        key, u', '.join(resp[key]), was_anticipated))
        #    if not was_anticipated:
        #        log.debug('\t%s => %s was anticipated instead.' % (
        #                  key, u', '.join(tests[key])))

        # Attempt to phonologize an empty list; expect a 400 error
        params = json.dumps({'transcriptions': []})
        response = self.app.put(url(controller='phonologies', action='applydown',
                                    id=phonology1_id),
                    params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['transcriptions'] == u'Please enter a value'

        # Attempt to phonologize an improperly formatted JSON string; expect a 400 error
        params = json.dumps({'transcriptions': [u'nit-wa']})[:-2]
        response = self.app.put(url(controller='phonologies', action='applydown',
                                    id=phonology1_id),
                    params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp == h.JSONDecodeErrorResponse

        # Attempt to phonologize with a non-existent phonology id; expect to fail
        params = json.dumps({'transcriptions': u'nit-wa'})
        response = self.app.put(url(controller='phonologies', action='applydown',
                                    id=123456789), params, self.json_headers,
                                self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no phonology with id 123456789'

        # Attempt to phonologize with a phonology whose script has not been compiled;
        # expect to fail.
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology 2',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology2_id = resp['id']

        params = json.dumps({'transcriptions': u'nit-wa'})
        response = self.app.put(url(controller='phonologies', action='applydown',
                                    id=phonology2_id), params, self.json_headers,
                                self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'Phonology %d has not been compiled yet.' % phonology2_id

    @nottest
    def test_runtests(self):
        """Tests that ``GET /phonologies/id/runtests`` runs the tests in the phonology's script."""

        # Create a phonology with the test phonology script
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology1_id = resp['id']
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % phonology1_id)
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_phonology_script
        assert resp['modifier']['role'] == u'administrator'

        # If foma is not installed, make sure the error message is being returned
        # and exit the test.
        if not h.foma_installed(force_check=True):
            response = self.app.get(url(controller='phonologies',
                        action='runtests', id=phonology1_id), headers=self.json_headers,
                        extra_environ=self.extra_environ_admin, status=400)
            resp = json.loads(response.body)
            assert resp['error'] == u'Foma and flookup are not installed.'
            return

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology1_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']
        compile_succeeded = resp['compile_succeeded']
        compile_message = resp['compile_message']

        # Poll ``GET /phonologies/phonology1_id`` until ``compile_attempt`` has changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1_id)
            sleep(1)

        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonology_binary_filename in os.listdir(phonology_dir)
        assert resp['modifier']['role'] == u'contributor'

        # Request the tests be run.
        response = self.app.get(url(controller='phonologies', action='runtests',
                    id=phonology1_id), headers=self.json_headers,
                    extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp.keys()
        assert 'expected' in resp.values()[0] and 'actual' in resp.values()[0]
        # Just for interest's sake, let's see how many tests were correct
        correct = total = 0
        incorrect = []
        for t in resp:
            for e in resp[t]['expected']:
                if e in resp[t]['actual']:
                    correct = correct + 1
                else:
                    incorrect.append((t, e))
                total = total + 1
        log.debug('%d/%d phonology tests passed (%0.2f%s)' % (
            correct, total, 100 * (correct/float(total)), '%'))
        for t, e in incorrect:
            log.debug('%s expected to be %s but phonology returned %s' % (
                t, e, ', '.join(resp[t]['actual'])))

        # Try to request GET /phonologies/id/runtests on a phonology with no tests.

        # Create the test-less phonology.
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology 2',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.test_phonology_testless_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology1_id = resp['id']
        phonology_dir = os.path.join(self.phonologies_path, 'phonology_%d' % phonology1_id)
        phonology_dir_contents = os.listdir(phonology_dir)
        phonology_binary_filename = 'phonology.foma'
        assert resp['name'] == u'Blackfoot Phonology 2'
        assert 'phonology.script' in phonology_dir_contents
        assert 'phonology.sh' in phonology_dir_contents
        assert phonology_binary_filename not in phonology_dir_contents
        assert response.content_type == 'application/json'
        assert resp['script'] == self.test_phonology_testless_script
        assert resp['modifier']['role'] == u'administrator'

        # Compile the phonology's script
        response = self.app.put(url(controller='phonologies', action='compile', id=phonology1_id),
                                headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']

        # Poll ``GET /phonologies/phonology1_id`` until ``compile_attempt`` has changed.
        while True:
            response = self.app.get(url('phonology', id=phonology1_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for phonology %d has terminated.' % phonology1_id)
                break
            else:
                log.debug('Waiting for phonology %d to compile ...' % phonology1_id)
            sleep(1)

        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert phonology_binary_filename in os.listdir(phonology_dir)
        assert resp['modifier']['role'] == u'contributor'

        # Request the tests be run.
        response = self.app.get(url(controller='phonologies', action='runtests',
                    id=phonology1_id), headers=self.json_headers,
                    extra_environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The script of phonology %d contains no tests.' % phonology1_id

    @nottest
    def test_history(self):
        """Tests that GET /phonologies/id/history returns the phonology with id=id and its previous incarnations.

        The JSON object returned is of the form
        {'phonology': phonology, 'previous_versions': [...]}.

        """

        users = h.get_users()
        contributor_id = [u for u in users if u.role==u'contributor'][0].id
        administrator_id = [u for u in users if u.role==u'administrator'][0].id

        # Create a phonology.
        original_phonology_count = Session.query(Phonology).count()
        params = self.phonology_create_params.copy()
        original_script = u'# The rules will begin after this comment.\n\n'
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': original_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_count = Session.query(Phonology).count()
        phonology_id = resp['id']
        original_datetime_modified = resp['datetime_modified']
        assert phonology_count == original_phonology_count + 1
        assert resp['name'] == u'Phonology'
        assert resp['description'] == u'Covers a lot of the data.'

        # Update the phonology as the admin.
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        new_script = u'define phonology o -> 0 || t "-" _ k "-";'
        orig_backup_count = Session.query(PhonologyBackup).count()
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.  Best yet!',
            'script': new_script
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonology_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        new_backup_count = Session.query(PhonologyBackup).count()
        first_update_datetime_modified = datetime_modified = resp['datetime_modified']
        new_phonology_count = Session.query(Phonology).count()
        assert phonology_count == new_phonology_count
        assert datetime_modified != original_datetime_modified
        assert resp['description'] == u'Covers a lot of the data.  Best yet!'
        assert resp['script'] == new_script
        assert response.content_type == 'application/json'
        assert orig_backup_count + 1 == new_backup_count
        backup = Session.query(PhonologyBackup).filter(
            PhonologyBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(PhonologyBackup.id)).first()
        assert backup.datetime_modified.isoformat() == original_datetime_modified
        assert backup.script == original_script
        assert json.loads(backup.modifier)['first_name'] == u'Admin'
        assert response.content_type == 'application/json'

        # Update the phonology as the contributor.
        sleep(1)    # sleep for a second to ensure that MySQL could register a different datetime_modified for the update
        newest_script = u'define phonology o -> 0 || k "-" _ k "-";'
        orig_backup_count = Session.query(PhonologyBackup).count()
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers even more data.  Better than ever!',
            'script': newest_script
        })
        params = json.dumps(params)
        response = self.app.put(url('phonology', id=phonology_id), params, self.json_headers,
                                 self.extra_environ_contrib)
        resp = json.loads(response.body)
        backup_count = new_backup_count
        new_backup_count = Session.query(PhonologyBackup).count()
        datetime_modified = resp['datetime_modified']
        new_phonology_count = Session.query(Phonology).count()
        assert phonology_count == new_phonology_count == 1
        assert datetime_modified != original_datetime_modified
        assert resp['description'] == u'Covers even more data.  Better than ever!'
        assert resp['script'] == newest_script
        assert resp['modifier']['id'] == contributor_id
        assert response.content_type == 'application/json'
        assert backup_count + 1 == new_backup_count
        backup = Session.query(PhonologyBackup).filter(
            PhonologyBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(PhonologyBackup.id)).first()
        assert backup.datetime_modified.isoformat() == first_update_datetime_modified
        assert backup.script == new_script
        assert json.loads(backup.modifier)['first_name'] == u'Admin'
        assert response.content_type == 'application/json'

        # Now get the history of this phonology.
        extra_environ = {'test.authentication.role': u'contributor',
                         'test.application_settings': True}
        response = self.app.get(
            url(controller='phonologies', action='history', id=phonology_id),
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'phonology' in resp
        assert 'previous_versions' in resp
        first_version = resp['previous_versions'][1]
        second_version = resp['previous_versions'][0]
        current_version = resp['phonology']

        assert first_version['name'] == u'Phonology'
        assert first_version['description'] == u'Covers a lot of the data.'
        assert first_version['enterer']['id'] == administrator_id
        assert first_version['modifier']['id'] == administrator_id
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert first_version['datetime_modified'] <= second_version['datetime_modified']

        assert second_version['name'] == u'Phonology'
        assert second_version['description'] == u'Covers a lot of the data.  Best yet!'
        assert second_version['script'] == new_script
        assert second_version['enterer']['id'] == administrator_id
        assert second_version['modifier']['id'] == administrator_id
        assert second_version['datetime_modified'] <= current_version['datetime_modified']

        assert current_version['name'] == u'Phonology'
        assert current_version['description'] == u'Covers even more data.  Better than ever!'
        assert current_version['script'] == newest_script
        assert current_version['enterer']['id'] == administrator_id
        assert current_version['modifier']['id'] == contributor_id

        # Get the history using the phonology's UUID and expect it to be the same
        # as the one retrieved above
        phonology_UUID = resp['phonology']['UUID']
        response = self.app.get(
            url(controller='phonologies', action='history', id=phonology_UUID),
            headers=self.json_headers, extra_environ=extra_environ)
        resp_UUID = json.loads(response.body)
        assert resp == resp_UUID

        # Attempt to call history with an invalid id and an invalid UUID and
        # expect 404 errors in both cases.
        bad_id = 103
        bad_UUID = str(uuid4())
        response = self.app.get(
            url(controller='phonologies', action='history', id=bad_id),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No phonologies or phonology backups match %d' % bad_id
        response = self.app.get(
            url(controller='phonologies', action='history', id=bad_UUID),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No phonologies or phonology backups match %s' % bad_UUID

        # Now delete the phonology ...
        response = self.app.delete(url('phonology', id=phonology_id),
                        headers=self.json_headers, extra_environ=extra_environ)

        # ... and get its history again, this time using the phonology's UUID
        response = self.app.get(
            url(controller='phonologies', action='history', id=phonology_UUID),
            headers=self.json_headers, extra_environ=extra_environ)
        by_UUID_resp = json.loads(response.body)
        assert by_UUID_resp['phonology'] == None
        assert len(by_UUID_resp['previous_versions']) == 3
        first_version = by_UUID_resp['previous_versions'][2]
        second_version = by_UUID_resp['previous_versions'][1]
        third_version = by_UUID_resp['previous_versions'][0]

        assert first_version['name'] == u'Phonology'
        assert first_version['description'] == u'Covers a lot of the data.'
        assert first_version['enterer']['id'] == administrator_id
        assert first_version['modifier']['id'] == administrator_id
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert first_version['datetime_modified'] <= second_version['datetime_modified']

        assert second_version['name'] == u'Phonology'
        assert second_version['description'] == u'Covers a lot of the data.  Best yet!'
        assert second_version['script'] == new_script
        assert second_version['enterer']['id'] == administrator_id
        assert second_version['modifier']['id'] == administrator_id
        assert second_version['datetime_modified'] <= third_version['datetime_modified']

        assert third_version['name'] == u'Phonology'
        assert third_version['description'] == u'Covers even more data.  Better than ever!'
        assert third_version['script'] == newest_script
        assert third_version['enterer']['id'] == administrator_id
        assert third_version['modifier']['id'] == contributor_id

        # Get the deleted phonology's history again, this time using its id.  The 
        # response should be the same as the response received using the UUID.
        response = self.app.get(
            url(controller='phonologies', action='history', id=phonology_id),
            headers=self.json_headers, extra_environ=extra_environ)
        by_phonology_id_resp = json.loads(response.body)
        assert by_phonology_id_resp == by_UUID_resp
