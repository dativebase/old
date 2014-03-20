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

import datetime
import logging
import simplejson as json
import os
from base64 import b64encode
from nose.tools import nottest
from mimetypes import guess_type
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder

try:
    import Image
except ImportError:
    Image = None

log = logging.getLogger(__name__)

class TestFilesController(TestController):

    def tearDown(self):
        TestController.tearDown(self, del_global_app_set=True,
                dirs_to_clear=['files_path', 'reduced_files_path'])

    @nottest
    def test_index(self):
        """Tests that GET /files returns a JSON array of files with expected values."""
        # Test that the restricted tag is working correctly.
        # First get the users.
        users = h.get_users()
        contributor_id = [u for u in users if u.role == u'contributor'][0].id

        # Then add a contributor and a restricted tag.
        restricted_tag = h.generate_restricted_tag()
        my_contributor = h.generate_default_user()
        my_contributor_first_name = u'Mycontributor'
        my_contributor.first_name = my_contributor_first_name
        Session.add_all([restricted_tag, my_contributor])
        Session.commit()
        my_contributor = Session.query(model.User).filter(
            model.User.first_name == my_contributor_first_name).first()
        my_contributor_id = my_contributor.id
        restricted_tag = h.get_restricted_tag()

        # Then add the default application settings with my_contributor as the
        # only unrestricted user.
        application_settings = h.generate_default_application_settings()
        application_settings.unrestricted_users = [my_contributor]
        Session.add(application_settings)
        Session.commit()

        # Finally, issue two POST requests to create two default files with the
        # *default* contributor as the enterer.  One file will be restricted and
        # the other will not be.
        extra_environ = {'test.authentication.id': contributor_id,
                         'test.application_settings': True}

        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        wav_file_base64_encoded = b64encode(open(wav_file_path).read())

        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        jpg_file_base64_encoded = b64encode(open(jpg_file_path).read())

        # Create the restricted file.
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'test_restricted_file.wav',
            'base64_encoded_file': wav_file_base64_encoded,
            'tags': [h.get_tags()[0].id]    # the restricted tag should be the only one
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restricted_file_id = resp['id']

        # Create the unrestricted file.
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'test_unrestricted_file.jpg',
            'base64_encoded_file': jpg_file_base64_encoded
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)

        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted my_contributor should all be able to view both files.
        # The viewer will only receive the unrestricted file.

        # An administrator should be able to view both files.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.application_settings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert resp[0]['filename'] == u'test_restricted_file.wav'
        assert resp[1]['filename'] == u'test_unrestricted_file.jpg'
        assert response.content_type == 'application/json'

        # The default contributor (qua enterer) should also be able to view both
        # files.
        extra_environ = {'test.authentication.id': contributor_id,
                         'test.application_settings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Mycontributor (an unrestricted user) should also be able to view both
        # files.
        extra_environ = {'test.authentication.id': my_contributor_id,
                         'test.application_settings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # A (not unrestricted) viewer should be able to view only one file.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.application_settings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove Mycontributor from the unrestricted users list and access to
        # the second file will be denied.
        application_settings = h.get_application_settings()
        application_settings.unrestricted_users = []
        Session.add(application_settings)
        Session.commit()

        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view the restricted file.
        extra_environ = {'test.authentication.id': my_contributor_id,
                         'test.application_settings': True,
                         'test.retain_application_settings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove the restricted tag from the file and the viewer should now be
        # able to view it too.
        restricted_file = Session.query(model.File).get(restricted_file_id)
        restricted_file.tags = []
        Session.add(restricted_file)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.application_settings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Clear all Files (actually, everything but the tags, users and languages)
        h.clear_all_models(['User', 'Tag', 'Language'])

        # Now add 100 files.  The even ones will be restricted, the odd ones not.
        # These files will be deficient, i.e., have no binary data or MIME_type
        # but that's ok ...
        def create_file_from_index(index):
            file = model.File()
            file.filename = u'name_%d.jpg' % index
            return file
        files = [create_file_from_index(i) for i in range(1, 101)]
        Session.add_all(files)
        Session.commit()
        files = h.get_files()
        restricted_tag = h.get_restricted_tag()
        for file in files:
            if int(file.filename.split('_')[1].split('.')[0]) % 2 == 0:
                file.tags.append(restricted_tag)
            Session.add(file)
        Session.commit()
        files = h.get_files()    # ordered by File.id ascending

        # An administrator should be able to retrieve all of the files.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.application_settings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['filename'] == u'name_1.jpg'
        assert resp[0]['id'] == files[0].id

        # Test the paginator GET params.
        paginator = {'items_per_page': 23, 'page': 3}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['filename'] == files[46].filename

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'File', 'order_by_attribute': 'filename',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('files'), order_by_params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        result_set = sorted([f.filename for f in files], reverse=True)
        assert result_set == [f['filename'] for f in resp]
        assert response.content_type == 'application/json'

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'File', 'order_by_attribute': 'filename',
                     'order_by_direction': 'desc', 'items_per_page': 23, 'page': 3}
        response = self.app.get(url('files'), params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert result_set[46] == resp['items'][0]['filename']

        # The default viewer should only be able to see the odd numbered files,
        # even with a paginator.
        items_per_page = 7
        page = 7
        paginator = {'items_per_page': items_per_page, 'page': page}
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.application_settings': True}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == items_per_page
        assert resp['items'][0]['filename'] == u'name_%d.jpg' % (
            ((items_per_page * (page - 1)) * 2) + 1)

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'File', 'order_by_attribute': 'filename',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('files'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"

        # Expect the default BY id ASCENDING ordering when the order_by_model/Attribute
        # param is invalid.
        order_by_params = {'order_by_model': 'Fileage', 'order_by_attribute': 'nom',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('files'), order_by_params,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp[0]['id'] == files[0].id

        # Expect a 400 error when the paginator GET params are empty, not
        # specified or integers that are less than 1
        paginator = {'items_per_page': u'a', 'page': u''}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'items_per_page': 0, 'page': -1}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['items_per_page'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    @nottest
    def test_create(self):
        """Tests that POST /files correctly creates a new file."""

        ########################################################################
        # base64-encoded file creation
        ########################################################################

        # Pass some mal-formed JSON to test that a 400 error is returned.
        params = '"a'   # Bad JSON
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'JSON decode error: the parameters provided were not valid JSON.'

        # Create a test audio file.
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        wav_file_size = os.path.getsize(wav_file_path)
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64_encoded_file': b64encode(open(wav_file_path).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert resp['filename'] == u'old_test.wav'
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert file_count == 1
        assert response.content_type == 'application/json'

        # Create a test image file.
        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        jpg_file_size = os.path.getsize(jpg_file_path)
        jpg_file_base64 = b64encode(open(jpg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': jpg_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        file_id = an_image_id = resp['id']
        assert resp['filename'] == u'old_test.jpg'
        assert resp['MIME_type'] == u'image/jpeg'
        assert resp['size'] == jpg_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert file_count == 2

        # Create a test image file with many-to-many relations, i.e., tags and
        # forms.  First create a couple of tags.
        tag1 = model.Tag()
        tag1.name = u'tag 1'
        tag2 = model.Tag()
        tag2.name = u'tag 2'
        restricted_tag = h.generate_restricted_tag()
        Session.add_all([tag1, tag2, restricted_tag])
        Session.commit()
        tag1_id = tag1.id
        tag2_id = tag2.id
        restricted_tag_id = restricted_tag.id

        # Then create a form to associate.
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'test',
            'translations': [{'transcription': u'test', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        form_id = resp['id']

        # Now create the file with forms and tags
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': jpg_file_base64,
            'tags': [tag1_id, tag2_id],
            'forms': [form_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert resp['filename'][:9] == u'old_test_'
        assert resp['MIME_type'] == u'image/jpeg'
        assert resp['size'] == jpg_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert sorted([t['id'] for t in resp['tags']]) == sorted([tag1_id, tag2_id])
        assert resp['forms'][0]['transcription'] == u'test'
        assert file_count == 3

        # Invalid input
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        wav_file_size = os.path.getsize(wav_file_path)
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'',                    # empty; not allowed
            'base64_encoded_file': '',        # empty; not allowed
            'utterance_type': u'l' * 1000,   # too long
            'date_elicited': '31/12/2012',   # wrong format
            'speaker': 200                  # invalid id
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert u'Value must be one of: None; Object Language Utterance; Metalanguage Utterance; Mixed Utterance' in \
            resp['errors']['utterance_type']
        assert resp['errors']['speaker'] == u'There is no speaker with id 200.'
        assert resp['errors']['date_elicited'] == u'Please enter a month from 1 to 12'
        assert resp['errors']['filename'] == u'Please enter a value'
        assert resp['errors']['base64_encoded_file']== u'Please enter a value'
        assert file_count == 3
        assert response.content_type == 'application/json'

        # Create an audio file with unicode characters.  Show that spaces are
        # replaced with underscores and that apostrophes and quotation marks are
        # removed.
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        wav_file_size = os.path.getsize(wav_file_path)
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'\u201Cold te\u0301st\u201D.wav',
            'base64_encoded_file': b64encode(open(wav_file_path).read()),
            'tags': [restricted_tag_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        a_wav_file_id = resp['id']
        file_count = Session.query(model.File).count()
        assert u'\u201Cold_te\u0301st\u201D.wav' in os.listdir(self.files_path)
        assert resp['filename'] == u'\u201Cold_te\u0301st\u201D.wav'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert file_count == 4
        assert restricted_tag_id in [t['id'] for t in resp['tags']]
        assert response.content_type == 'application/json'

        # Attempt to create an illicit file type (.html) but with a valid
        # extension (.wav).  Expect an error, i.e., validation detects that the
        # file is really html, despite the misleading extension.
        # WARNING: this (type of) test will fail of python-magic (and its dependency libmagic) is
        # not installed. This is because the file create validator will not recognize this
        # file as HTML pretending to be WAV
        files_dir_list = os.listdir(self.files_path)
        html_file_path = os.path.join(self.test_files_path, 'illicit.html')
        html_file_base64 = b64encode(open(html_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'pretend_its_wav.wav',
            'base64_encoded_file': html_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        new_files_dir_list = os.listdir(self.files_path)
        assert file_count == 4
        assert resp['errors'] == u"The file extension does not match the file's true type (audio/x-wav vs. text/html, respectively)."
        assert files_dir_list == new_files_dir_list

        ########################################################################
        # multipart/form-data file creation
        ########################################################################

        # Upload a file using the multipart/form-data Content-Type and a POST
        # request to /files.  Here we do not supply a filename POST param so the
        # files controller creates one based on the path automatically included
        # in filedata.  The controller removes the path separators of its os
        # when it creates the filename; however path separators from a foreign os
        # may remain in the generated filename.
        params = self.file_create_params_MPFD.copy()
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', wav_file_path)])
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert resp['filename'] in os.listdir(self.files_path)
        assert resp['filename'][:8] == u'old_test'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert file_count == 5
        assert response.content_type == 'application/json'

        # Upload a file using the multipart/form-data Content-Type and a POST
        # request to /files.  Here we do supply a filename and some metadata.
        params = self.file_create_params_MPFD.copy()
        params.update({
            'filename': u'wavfile.wav',
            'description': u'multipart/form-data',
            'date_elicited': u'12/03/2011',    # mm/dd/yyyy
            'utterance_type': u'Mixed Utterance',
            'tags-0': tag1_id,
            'tags-1': tag2_id,
            'forms-0': form_id
        })
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', wav_file_path)])
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert u'wavfile.wav' in os.listdir(self.files_path)
        assert resp['filename'] == u'wavfile.wav'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert sorted([t['id'] for t in resp['tags']]) == sorted([tag1_id, tag2_id])
        assert resp['forms'][0]['id'] == form_id
        assert resp['utterance_type'] == u'Mixed Utterance'
        assert resp['description'] == u'multipart/form-data'
        assert resp['date_elicited'] == u'2011-12-03'
        assert file_count == 6
        assert response.content_type == 'application/json'

        # Upload using multipart/form-data and attempt to pass a malicious
        # filename; the path separator should be removed from the filename.  If
        # the separator were not removed, this filename could cause the file to
        # be written to the parent directory of the files directory
        params = self.file_create_params_MPFD.copy()
        params.update({'filename': u'../wavfile.wav'})
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
            upload_files=[('filedata', wav_file_path)])
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        binary_files_list = os.listdir(self.files_path)
        binary_files_list_count = len(binary_files_list)
        assert u'..wavfile.wav' in binary_files_list
        assert resp['filename'] == u'..wavfile.wav'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert file_count == 7
        assert response.content_type == 'application/json'

        # Upload using multipart/form-data and attempt to pass an invalid file
        # type (.html) but with a valid extension (.wav).  Expect an error.
        html_file_path = os.path.join(self.test_files_path, 'illicit.html')
        files_dir_list = os.listdir(self.files_path)
        params = self.file_create_params_MPFD.copy()
        params.update({'filename': u'pretend_its_wav.wav'})
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
            upload_files=[('filedata', html_file_path)], status=400)
        resp = json.loads(response.body)
        new_file_count = Session.query(model.File).count()
        new_files_dir_list = os.listdir(self.files_path)
        assert file_count == new_file_count
        assert resp['errors'] == u"The file extension does not match the file's true type (audio/x-wav vs. text/html, respectively)."
        assert files_dir_list == new_files_dir_list

        # Try the same as above but instead of providing a deceitful filename in
        # the POST params, upload a file with a false extension.
        html_file_path = os.path.join(self.test_files_path, 'illicit.wav')
        files_dir_list = new_files_dir_list
        params = self.file_create_params_MPFD.copy()
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
            upload_files=[('filedata', html_file_path)], status=400)
        resp = json.loads(response.body)
        new_file_count = Session.query(model.File).count()
        new_files_dir_list = os.listdir(self.files_path)
        assert file_count == new_file_count
        assert resp['errors'] == u"The file extension does not match the file's true type (audio/x-wav vs. text/html, respectively)."
        assert files_dir_list == new_files_dir_list

        ########################################################################
        # Subinterval-Referencing File
        ########################################################################

        # Create a subinterval-referencing audio file; reference one of the wav
        # files created earlier.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': a_wav_file_id,
            'name': u'subinterval_x',
            'start': 1.3,
            'end': 2.6
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        new_binary_files_list = os.listdir(self.files_path)
        new_binary_files_list_count = len(new_binary_files_list)
        subinterval_referencing_id = resp['id']
        assert new_binary_files_list_count == binary_files_list_count
        assert u'\u201Cold_te\u0301st\u201D.wav' in new_binary_files_list
        assert u'subinterval_x' not in new_binary_files_list
        assert resp['filename'] == None
        assert resp['parent_file']['filename'] == u'\u201Cold_te\u0301st\u201D.wav'
        assert resp['name'] == u'subinterval_x'
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == None
        assert resp['parent_file']['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert resp['start'] == 1.3
        assert type(resp['start']) is float
        assert resp['end'] == 2.6
        assert type(resp['end']) is float
        assert file_count == 8
        assert response.content_type == 'application/json'

        # Attempt to create another subinterval-referencing audio file; fail
        # because name is too long, parent_file is empty, start is not a number
        # and end is unspecified
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'name': u'subinterval_x' * 200,
            'start': u'a',
            'end': None
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert file_count == 8   # unchanged
        assert resp['errors']['parent_file'] == u'An id corresponding to an existing audio or video file must be provided.'
        assert resp['errors']['start'] == u'Please enter a number'
        assert resp['errors']['end'] == u'Please enter a value'
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

        # Attempt to create another subinterval-referencing audio file; fail
        # because the contributor is not authorized to access the restricted parent_file.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': a_wav_file_id,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_contrib, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert file_count == 8
        assert resp['errors']['parent_file'] == u'You are not authorized to access the file with id %d.' % a_wav_file_id

        # Create another subinterval-referencing audio file; this one's parent is
        # restricted.  Note that it does not itself become restricted.  Note also
        # that a name is not required.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': a_wav_file_id,
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert file_count == 9
        assert resp['parent_file']['id'] == a_wav_file_id
        assert u'restricted' not in [t['name'] for t in resp['tags']]
        assert resp['name'] == resp['parent_file']['name']

        # Attempt to create another subinterval-referencing file; fail because
        # the parent file is not an A/V file.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': an_image_id,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert file_count == 9
        assert resp['errors']['parent_file'] == u'File %d is not an audio or a video file.' % an_image_id

        # Attempt to create another subinterval-referencing file; fail because
        # the parent file id is invalid
        bad_id = 1000009252345345
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': bad_id,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert file_count == 9
        assert resp['errors']['parent_file'] == u'There is no file with id %d.' % bad_id

        # Attempt to create another subinterval-referencing file; fail because
        # the parent file id is itself a subinterval-referencing file
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': subinterval_referencing_id,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert file_count == 9
        assert resp['errors']['parent_file'] == u'The parent file cannot itself be a subinterval-referencing file.'

        # Attempt to create a subinterval-referencing audio file; fail because
        # start >= end.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': a_wav_file_id,
            'name': u'subinterval_z',
            'start': 1.3,
            'end': 1.3
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert response.content_type == 'application/json'
        assert resp['errors'] == u'The start value must be less than the end value.'

        ########################################################################
        # externally hosted file creation
        ########################################################################

        # Create a valid externally hosted file
        params = self.file_create_params_ext_host.copy()
        url_ = 'http://vimeo.com/54144270'
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'MIME_type': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['description'] == u'A large video file I didn\'t want to upload here.'
        assert resp['url'] == url_

        # Attempt to create an externally hosted file with invalid params
        params = self.file_create_params_ext_host.copy()
        url_ = 'http://vimeo/541442705414427054144270541442705414427054144270'  # Invalid url
        params.update({
            'url': url_,
            'name': u'invalid externally hosted file',
            'MIME_type': u'video/gepm',      # invalid MIME_type
            'description': u'A large video file, sadly invalid.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['MIME_type'] == u'The file upload failed because the file type video/gepm is not allowed.'
        resp['errors']['url'] == u'You must provide a full domain name (like vimeo.com)'

        # Attempt to create an externally hosted file with different invalid params
        params = self.file_create_params_ext_host.copy()
        params.update({
            'url': u'',   # shouldn't be empty
            'name': u'invalid externally hosted file' * 200,    # too long
            'password': u'a87XS.1d9X837a001W2w3a87XS.1d9X837a001W2w3' * 200,    # too long
            'description': u'A large video file, sadly invalid.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['url'] == u'Please enter a value'
        assert resp['errors']['password'] == u'Enter a value not more than 255 characters long'
        assert resp['errors']['name'] ==  u'Enter a value not more than 255 characters long'

        # Show that the name param is optional
        params = self.file_create_params_ext_host.copy()
        url_ = 'http://vimeo.com/54144270'
        params.update({
            'url': url_,
            'MIME_type': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u''

    @nottest
    def test_relational_restrictions(self):
        """Tests that the restricted tag works correctly with respect to relational attributes of files.

        That is, tests that (a) file.forms does not return restricted forms to
        restricted users and (b) a restricted user cannot append a restricted
        form to file.forms."""

        admin = self.extra_environ_admin.copy()
        admin.update({'test.application_settings': True})
        contrib = self.extra_environ_contrib.copy()
        contrib.update({'test.application_settings': True})

        # Create a test audio file.
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        wav_file_size = os.path.getsize(wav_file_path)
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64_encoded_file': b64encode(open(wav_file_path).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert resp['filename'] == u'old_test.wav'
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert file_count == 1
        assert response.content_type == 'application/json'

        # First create the restricted tag.
        restricted_tag = h.generate_restricted_tag()
        Session.add(restricted_tag)
        Session.commit()
        restricted_tag_id = restricted_tag.id

        # Then create two forms, one restricted and one not.
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'restricted',
            'translations': [{'transcription': u'restricted', 'grammaticality': u''}],
            'tags': [restricted_tag_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 admin)
        resp = json.loads(response.body)
        restricted_form_id = resp['id']

        params = self.form_create_params.copy()
        params.update({
            'transcription': u'unrestricted',
            'translations': [{'transcription': u'unrestricted', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 admin)
        resp = json.loads(response.body)
        unrestricted_form_id = resp['id']

        # Now, as a (restricted) contributor, attempt to create a file and
        # associate it to a restricted form -- expect to fail.
        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        jpg_file_size = os.path.getsize(jpg_file_path)
        jpg_file_base64 = b64encode(open(jpg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': jpg_file_base64,
            'forms': [restricted_form_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the form with id %d.' % restricted_form_id in \
            resp['errors']['forms']

        # Now, as a (restricted) contributor, attempt to create a file and
        # associate it to an unrestricted form -- expect to succeed.
        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        jpg_file_size = os.path.getsize(jpg_file_path)
        jpg_file_base64 = b64encode(open(jpg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': jpg_file_base64,
            'forms': [unrestricted_form_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 contrib)
        resp = json.loads(response.body)
        unrestricted_file_id = resp['id']
        assert resp['filename'] == u'old_test.jpg'
        assert resp['forms'][0]['transcription'] == u'unrestricted'

        # Now, as a(n unrestricted) administrator, attempt to create a file and
        # associate it to a restricted form -- expect (a) to succeed and (b) to
        # find that the file is now restricted.
        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        jpg_file_base64 = b64encode(open(jpg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': jpg_file_base64,
            'forms': [restricted_form_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        indirectly_restricted_file_id = resp['id']
        assert resp['filename'][:8] == u'old_test'
        assert resp['forms'][0]['transcription'] == u'restricted'
        assert u'restricted' in [t['name'] for t in resp['tags']]

        # Now show that the indirectly restricted files are inaccessible to
        # unrestricted users.
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=contrib)
        resp = json.loads(response.body)
        assert indirectly_restricted_file_id not in [f['id'] for f in resp]

        # Now, as a(n unrestricted) administrator, create a file.
        unrestricted_file_params = self.file_create_params_base64.copy()
        unrestricted_file_params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': jpg_file_base64
        })
        params = json.dumps(unrestricted_file_params)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        unrestricted_file_id = resp['id']
        assert resp['filename'][:8] == u'old_test'
        assert response.content_type == 'application/json'

        # As a restricted contributor, attempt to update the unrestricted file
        # just created by associating it to a restricted form -- expect to fail.
        unrestricted_file_params.update({'forms': [restricted_form_id]})
        params = json.dumps(unrestricted_file_params)
        response = self.app.put(url('file', id=unrestricted_file_id), params,
                                self.json_headers, contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the form with id %d.' % restricted_form_id in \
            resp['errors']['forms']
        assert response.content_type == 'application/json'

        # As an unrestricted administrator, attempt to update an unrestricted file
        # by associating it to a restricted form -- expect to succeed.
        response = self.app.put(url('file', id=unrestricted_file_id), params,
                                self.json_headers, admin)
        resp = json.loads(response.body)
        assert resp['id'] == unrestricted_file_id
        assert u'restricted' in [t['name'] for t in resp['tags']]

        # Now show that the newly indirectly restricted file is also
        # inaccessible to an unrestricted user.
        response = self.app.get(url('file', id=unrestricted_file_id),
                headers=self.json_headers, extra_environ=contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

    @nottest
    def test_create_large(self):
        """Tests that POST /files correctly creates a large file.

        WARNING 1: long-running test.

        WARNING: 2: if a large file named old_test_long.wav does not exist in
        ``tests/data/files``, this test will pass vacuously.  I don't want to
        include such a large file in the code base so this file needs to be
        created if one wants this test to run.
        """

        file_count = new_file_count = Session.query(model.File).count()

        # Try to create a file with a > 20 MB file as content using JSON/Base64
        # encoding and expect to fail because the file is too big.
        long_wav_filename = 'old_test_long.wav'
        long_wav_file_path = os.path.join(self.test_files_path, long_wav_filename)
        if os.path.exists(long_wav_file_path):
            long_wav_file_size = os.path.getsize(long_wav_file_path)
            params = self.file_create_params_base64.copy()
            params.update({
                'filename': long_wav_filename,
                'base64_encoded_file': b64encode(open(long_wav_file_path).read())
            })
            params = json.dumps(params)
            response = self.app.post(url('files'), params, self.json_headers,
                                     self.extra_environ_admin, status=400)
            resp = json.loads(response.body)
            new_file_count = Session.query(model.File).count()
            assert file_count == new_file_count
            assert resp['error'] == u'The request body is too large; use the multipart/form-data Content-Type when uploading files greater than 20MB.'
            assert response.content_type == 'application/json'

        # Try to create a file with a ~6MB .wav file as content using JSON/Base64
        # encoding and expect to succeed because the file is < 20MB.
        medium_wav_filename = u'old_test_medium.wav'
        medium_wav_file_path = os.path.join(self.test_files_path, medium_wav_filename)
        if os.path.exists(medium_wav_file_path):
            old_reduced_dir_list = os.listdir(self.reduced_files_path)
            medium_wav_file_size = os.path.getsize(medium_wav_file_path)
            params = self.file_create_params_base64.copy()
            params.update({
                'filename': medium_wav_filename,
                'base64_encoded_file': b64encode(open(medium_wav_file_path).read())
            })
            params = json.dumps(params)
            response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
            resp = json.loads(response.body)
            file_count = new_file_count
            new_file_count = Session.query(model.File).count()
            new_reduced_dir_list = os.listdir(self.reduced_files_path)
            lossy_filename = '%s.%s' % (os.path.splitext(medium_wav_filename)[0],
                                       self.config.get('preferred_lossy_audio_format', 'ogg'))
            assert file_count + 1 == new_file_count
            assert resp['filename'] == medium_wav_filename
            assert resp['MIME_type'] == u'audio/x-wav'
            assert resp['size'] == medium_wav_file_size
            assert resp['enterer']['first_name'] == u'Admin'
            assert response.content_type == 'application/json'
            assert lossy_filename not in old_reduced_dir_list
            if self.create_reduced_size_file_copies and h.command_line_program_installed('ffmpeg'):
                assert resp['lossy_filename'] == lossy_filename
                assert lossy_filename in new_reduced_dir_list
            else:
                assert resp['lossy_filename'] == None
                assert lossy_filename not in new_reduced_dir_list

        # Create the large (> 20MB) .wav file from above using the multipart/form-data
        # POST method.
        if os.path.exists(long_wav_file_path):
            long_wav_file_size = os.path.getsize(long_wav_file_path)
            params = self.file_create_params_MPFD.copy()
            params.update({'filename': long_wav_filename})
            response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', long_wav_file_path)])
            resp = json.loads(response.body)
            file_count = new_file_count
            new_file_count = Session.query(model.File).count()
            new_reduced_dir_list = os.listdir(self.reduced_files_path)
            lossy_filename = '%s.%s' % (os.path.splitext(long_wav_filename)[0],
                                       self.config.get('preferred_lossy_audio_format', 'ogg'))
            assert file_count + 1 == new_file_count
            assert resp['filename'] == long_wav_filename
            assert resp['MIME_type'] == u'audio/x-wav'
            assert resp['size'] == long_wav_file_size
            assert resp['enterer']['first_name'] == u'Admin'
            assert response.content_type == 'application/json'
            assert lossy_filename not in old_reduced_dir_list
            if self.create_reduced_size_file_copies and h.command_line_program_installed('ffmpeg'):
                assert resp['lossy_filename'] == lossy_filename
                assert lossy_filename in new_reduced_dir_list
            else:
                assert resp['lossy_filename'] == None
                assert lossy_filename not in new_reduced_dir_list
    @nottest
    def test_new(self):
        """Tests that GET /file/new returns an appropriate JSON object for creating a new OLD file.

        The properties of the JSON object are 'tags', 'utterance_types',
        'speakers'and 'users' and their values are arrays/lists.
        """

        # Unauthorized user ('viewer') should return a 403 status code on the
        # new action, which requires a 'contributor' or an 'administrator'.
        extra_environ = {'test.authentication.role': 'viewer'}
        response = self.app.get(url('new_file'), extra_environ=extra_environ,
                                status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Add some test data to the database.
        application_settings = h.generate_default_application_settings()
        restricted_tag = h.generate_restricted_tag()
        speaker = h.generate_default_speaker()
        Session.add_all([application_settings, restricted_tag, speaker])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'tags': h.get_mini_dicts_getter('Tag')(),
            'speakers': h.get_mini_dicts_getter('Speaker')(),
            'users': h.get_mini_dicts_getter('User')(),
            'utterance_types': h.utterance_types,
            'allowed_file_types': h.allowed_file_types
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # GET /file/new without params.  Without any GET params, /file/new
        # should return a JSON array for every store.
        response = self.app.get(url('new_file'),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['tags'] == data['tags']
        assert resp['speakers'] == data['speakers']
        assert resp['users'] == data['users']
        assert resp['utterance_types'] == data['utterance_types']
        assert resp['allowed_file_types'] == data['allowed_file_types']
        assert response.content_type == 'application/json'

        # GET /new_file with params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetime_modified value of the
        #    store in question.
        params = {
            # Value is any string: 'speakers' will be in response.
            'speakers': 'anything can go here!',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent User.datetime_modified value: 'users' *will* be in
            # response.
            'users': datetime.datetime.utcnow().isoformat(),
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent Tag.datetime_modified value: 'tags' will *not* be in response.
            'tags': h.get_most_recent_modification_datetime('Tag').isoformat()
        }
        response = self.app.get(url('new_file'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['tags'] == []
        assert resp['speakers'] == data['speakers']
        assert resp['users'] == data['users']
        assert resp['utterance_types'] == data['utterance_types']
        assert response.content_type == 'application/json'

    @nottest
    def test_update(self):
        """Tests that PUT /files/id correctly updates an existing file."""

        file_count = Session.query(model.File).count()

        # Add the default application settings and the restricted tag.
        restricted_tag = h.generate_restricted_tag()
        application_settings = h.generate_default_application_settings()
        Session.add_all([application_settings, restricted_tag])
        Session.commit()
        restricted_tag = h.get_restricted_tag()
        restricted_tag_id = restricted_tag.id

        # Create a file to update.
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        wav_file_size = os.path.getsize(wav_file_path)
        params = self.file_create_params_base64.copy()

        original_name = u'test_update_name.wav'
        params.update({
            'filename': original_name,
            'tags': [restricted_tag.id],
            'description': u'description',
            'base64_encoded_file': b64encode(open(wav_file_path).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        id = int(resp['id'])
        new_file_count = Session.query(model.File).count()
        assert resp['filename'] == original_name
        assert new_file_count == file_count + 1

        # As a viewer, attempt to update the restricted file we just created.
        # Expect to fail.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.application_settings': True}
        params = self.file_create_params_base64.copy()
        params.update({
            'description': u'A file that has been updated.',
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=id), params,
            self.json_headers, extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # As an administrator now, update the file just created and expect to
        # succeed.
        params = self.file_create_params_base64.copy()
        params.update({
            'description': u'A file that has been updated.'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=id), params,
                                self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_file_count = Session.query(model.File).count()
        assert resp['description'] == u'A file that has been updated.'
        assert resp['tags'] == []
        assert new_file_count == file_count + 1
        assert response.content_type == 'application/json'

        # Attempt an update with no new data.  Expect a 400 error
        # and response['errors'] = {'no change': The update request failed
        # because the submitted data were not new.'}.
        response = self.app.put(url('file', id=id), params, self.json_headers,
                                self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'the submitted data were not new' in resp['error']

        # Add a speaker and some tags to the db.
        speaker = h.generate_default_speaker()
        tag1 = model.Tag()
        tag1.name = u'tag 1'
        tag2 = model.Tag()
        tag2.name = u'tag 2'
        Session.add_all([speaker, tag1, tag2])
        Session.commit()
        speaker = h.get_speakers()[0]
        tag1_id = tag1.id
        tag2_id = tag2.id
        speaker_id = speaker.id

        # Now update our file by adding a many-to-one datum, viz. a speaker
        params = self.file_create_params_base64.copy()
        params.update({'speaker': speaker.id})
        params = json.dumps(params)
        response = self.app.put(url('file', id=id), params, self.json_headers,
                                 extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['speaker']['first_name'] == speaker.first_name

        # Finally, update the file by adding some many-to-many data, i.e., tags
        params = self.file_create_params_base64.copy()
        params.update({'tags': [tag1_id, tag2_id]})
        params = json.dumps(params)
        response = self.app.put(url('file', id=id), params, self.json_headers,
                                 extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert sorted([t['name'] for t in resp['tags']]) == [u'tag 1', u'tag 2']

        ########################################################################
        # Updating "Plain Files"
        ########################################################################

        # Create a file using the multipart/form-data POST method.
        params = self.file_create_params_MPFD.copy()
        params.update({'filename': u'multipart.wav'})
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', wav_file_path)])
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        plain_file_id = resp['id']
        assert resp['filename'] == u'multipart.wav'
        assert resp['filename'] in os.listdir(self.files_path)
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['enterer']['first_name'] == u'Admin'
        assert response.content_type == 'application/json'

        # Update the plain file by adding some metadata.
        params = self.file_create_params_base64.copy()
        params.update({
            'tags': [tag1_id, tag2_id],
            'description': u'plain updated',
            'date_elicited': u'01/01/2000',
            'speaker': speaker_id,
            'utterance_type': u'Metalanguage Utterance'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=plain_file_id), params, self.json_headers,
                                 extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert sorted([t['name'] for t in resp['tags']]) == [u'tag 1', u'tag 2']
        assert resp['description'] == u'plain updated'
        assert resp['speaker']['id'] == speaker_id
        assert resp['filename'] == resp['name'] == u'multipart.wav'
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['enterer']['first_name'] == u'Admin'
        assert response.content_type == 'application/json'

        ########################################################################
        # Update a subinterval-referencing file
        ########################################################################

        # Create a subinterval-referencing audio file; reference one of the wav
        # files created earlier.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': plain_file_id,
            'name': u'anyname',
            'start': 13.3,
            'end': 26.89,
            'tags': [tag1_id],
            'description': u'subinterval-referencing file',
            'date_elicited': u'01/01/2000',
            'speaker': speaker_id,
            'utterance_type': u'Object Language Utterance'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_contrib)
        resp = json.loads(response.body)
        subinterval_referencing_id = resp['id']
        assert resp['filename'] == None
        assert resp['name'] == u'anyname'
        assert resp['parent_file']['filename'] == u'multipart.wav'
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == None
        assert resp['parent_file']['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Contributor'
        assert resp['start'] == 13.3
        assert type(resp['start']) is float
        assert resp['end'] == 26.89
        assert type(resp['end']) is float
        assert resp['tags'][0]['id'] == tag1_id
        assert response.content_type == 'application/json'

        # Update the subinterval-referencing file.
        params = self.file_create_params_base64.copy()
        params.update({
            'parent_file': plain_file_id,
            'start': 13.3,
            'end': 26.89,
            'tags': [],
            'description': u'abc to def',
            'date_elicited': u'01/01/2010',
            'utterance_type': u'Metalanguage Utterance'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=subinterval_referencing_id), params, self.json_headers,
                                 extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['parent_file']['id'] == plain_file_id
        assert resp['name'] == resp['parent_file']['name']
        assert resp['tags'] == []
        assert resp['description'] == u'abc to def'
        assert resp['speaker'] == None
        assert resp['MIME_type'] == u'audio/x-wav'
        assert response.content_type == 'application/json'

        # Attempt a vacuous update and expect an error message.
        response = self.app.put(url('file', id=subinterval_referencing_id), params, self.json_headers,
                                 extra_environ=self.extra_environ_contrib, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The update request failed because the submitted data were not new.'

        # Now restrict the parent file and verify that the child file does not
        # thereby become restricted.  This means that the metadata of a restricted
        # parent file may accessible to restricted users via the child file;
        # however, this is ok since the serve action still will not allow
        # the contents of the restricted file to be served to the restricted users.
        params = self.file_create_params_base64.copy()
        params.update({
            'tags': [tag1_id, tag2_id, restricted_tag_id],
            'description': u'plain updated',
            'date_elicited': u'01/01/2000',
            'speaker': speaker_id,
            'utterance_type': u'Metalanguage Utterance'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=plain_file_id), params,
                    self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert u'restricted' in [t['name'] for t in resp['tags']]

        SRFile = Session.query(model.File).get(subinterval_referencing_id)
        assert u'restricted' not in [t.name for t in SRFile.tags]

        ########################################################################
        # externally hosted file creation
        ########################################################################

        # Create a valid externally hosted file
        url_ = 'http://vimeo.com/54144270'
        params = self.file_create_params_ext_host.copy()
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'MIME_type': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['description'] == u'A large video file I didn\'t want to upload here.'
        assert resp['url'] == url_

        # Update the externally hosted file
        params = self.file_create_params_ext_host.copy()
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'password': u'abc',
            'MIME_type': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.',
            'date_elicited': u'12/29/1987'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['date_elicited'] == u'1987-12-29'
        assert resp['password'] == u'abc'

        # Attempt to update the externally hosted file with invalid params.
        params = self.file_create_params_ext_host.copy()
        params.update({
            'url': u'abc',      # Invalid
            'name': u'externally hosted file' * 200,    # too long
            'MIME_type': u'zooboomafoo',                 # invalid
            'description': u'A large video file I didn\'t want to upload here.',
            'date_elicited': u'1987/12/29'               # wrong format
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['MIME_type'] == u'The file upload failed because the file type zooboomafoo is not allowed.'
        assert resp['errors']['url'] == u'You must provide a full domain name (like abc.com)'
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert resp['errors']['date_elicited'] == u'Please enter the date in the form mm/dd/yyyy'

    @nottest
    def test_delete(self):
        """Tests that DELETE /files/id deletes the file with id=id and returns a JSON representation.

        If the id is invalid or unspecified, then JSON null or a 404 status code
        are returned, respectively.
        """
        # Add some objects to the db: a default application settings, a speaker
        # and a tag.
        application_settings = h.generate_default_application_settings()
        speaker = h.generate_default_speaker()
        my_contributor = h.generate_default_user()
        my_contributor.username = u'uniqueusername'
        tag = model.Tag()
        tag.name = u'default tag'
        Session.add_all([application_settings, speaker, my_contributor, tag])
        Session.commit()
        my_contributor = Session.query(model.User).filter(
            model.User.username==u'uniqueusername').first()
        my_contributor_id = my_contributor.id
        tag_id = tag.id
        speaker_id = speaker.id

        # Count the original number of files
        file_count = Session.query(model.File).count()

        # First, as my_contributor, create a file to delete.
        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        extra_environ = {'test.authentication.id': my_contributor_id,
                         'test.application_settings': True}
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'test_delete.jpg',
            'base64_encoded_file': b64encode(open(jpg_file_path).read()),
            'speaker': speaker_id,
            'tags': [tag_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        to_delete_id = resp['id']
        to_delete_name = resp['filename']
        assert resp['filename'] == u'test_delete.jpg'
        assert resp['tags'][0]['name'] == u'default tag'

        # Now count the files
        new_file_count = Session.query(model.File).count()
        assert new_file_count == file_count + 1

        # Now, as the default contributor, attempt to delete the my_contributor-
        # entered file we just created and expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.application_settings': True}
        response = self.app.delete(url('file', id=to_delete_id),
                                   extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        file_that_was_not_deleted = Session.query(model.File).get(to_delete_id)
        file_path = os.path.join(self.files_path, to_delete_name)
        assert os.path.exists(file_path)
        assert file_that_was_not_deleted is not None
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # As my_contributor, attempt to delete the file we just created and
        # expect to succeed.
        extra_environ = {'test.authentication.id': my_contributor_id,
                         'test.application_settings': True}
        response = self.app.delete(url('file', id=to_delete_id),
                                   extra_environ=extra_environ)
        resp = json.loads(response.body)
        new_file_count = Session.query(model.File).count()
        tag_of_deleted_file = Session.query(model.Tag).get(
            resp['tags'][0]['id'])
        speaker_of_deleted_file = Session.query(model.Speaker).get(
            resp['speaker']['id'])
        assert isinstance(tag_of_deleted_file, model.Tag)
        assert isinstance(speaker_of_deleted_file, model.Speaker)
        assert new_file_count == file_count

        # The deleted file will be returned to us, so the assertions from above
        # should still hold true.
        file_that_was_deleted = Session.query(model.File).get(to_delete_id)
        file_path = os.path.join(self.files_path, to_delete_name)
        assert not os.path.exists(file_path)
        assert 'old_test.jpg' not in os.listdir(self.files_path)
        assert file_that_was_deleted is None
        assert resp['filename'] == u'test_delete.jpg'

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('file', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no file with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # Delete without an id
        response = self.app.delete(url('file', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Create and delete a file with unicode characters in the file name
        extra_environ = {'test.authentication.id': my_contributor_id,
                         'test.application_settings': True}
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'\u201Cte\u0301st delete\u201D.jpg',
            'base64_encoded_file': b64encode(open(jpg_file_path).read()),
            'speaker': speaker_id,
            'tags': [tag_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ)
        resp = json.loads(response.body)
        to_delete_id = resp['id']
        to_delete_name = resp['filename']
        assert resp['filename'] == u'\u201Cte\u0301st_delete\u201D.jpg'
        assert resp['tags'][0]['name'] == u'default tag'
        assert u'\u201Cte\u0301st_delete\u201D.jpg' in os.listdir(self.files_path)
        response = self.app.delete(url('file', id=to_delete_id), extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert u'\u201Cte\u0301st_delete\u201D.jpg' not in os.listdir(self.files_path)

        # Create a file, create a subinterval-referencing file that references
        # it and then delete the parent file.  Show that the child files become
        # "orphaned" but are not deleted.  Use case: user has uploaded an incorrect
        # parent file; must delete parent file, create a new one and then update
        # child files' parent_file attribute.

        # Create the parent WAV file.
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'parent.wav',
            'base64_encoded_file': b64encode(open(wav_file_path).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        parent_id = resp['id']
        parent_filename = resp['filename']
        parent_lossy_filename = resp['lossy_filename']

        # Create a subinterval-referencing audio file; reference one of the wav
        # files created earlier.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': parent_id,
            'name': u'child',
            'start': 1,
            'end': 2,
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        child_id = resp['id']
        assert resp['parent_file']['id'] == parent_id

        # Show that the child file still exists after the parent has been deleted.
        assert parent_filename in os.listdir(self.files_path)
        if self.create_reduced_size_file_copies and h.command_line_program_installed('ffmpeg'):
            assert parent_lossy_filename in os.listdir(self.reduced_files_path)
        response = self.app.delete(url('file', id=parent_id), extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert parent_filename not in os.listdir(self.files_path)
        assert parent_lossy_filename not in os.listdir(self.reduced_files_path)
        assert resp['filename'] == u'parent.wav'

        parent = Session.query(model.File).get(parent_id)
        assert parent is None

        child = Session.query(model.File).get(child_id)
        assert child is not None
        assert child.parent_file is None

        # Delete the child file
        response = self.app.delete(url('file', id=child_id), extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'child'

    @nottest
    def test_show(self):
        """Tests that GET /files/id returns a JSON file object, null or 404
        depending on whether the id is valid, invalid or unspecified,
        respectively.
        """

        # First create a test image file.
        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        jpg_file_size = os.path.getsize(jpg_file_path)
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': b64encode(open(jpg_file_path).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        file_id = resp['id']
        assert resp['filename'] == u'old_test.jpg'
        assert resp['MIME_type'] == u'image/jpeg'
        assert resp['size'] == jpg_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert file_count == 1

        # Then create a form associated to the image file just created and make sure
        # we can access the form via the file.forms backreference.
        params = self.form_create_params.copy()
        params.update({
            'transcription': u'test',
            'translations': [{'transcription': u'test', 'grammaticality': u''}],
            'files': [file_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        assert type(resp) == type({})
        assert resp['transcription'] == u'test'
        assert resp['translations'][0]['transcription'] == u'test'
        assert resp['morpheme_break_ids'] == None
        assert resp['enterer']['first_name'] == u'Admin'
        assert resp['files'][0]['filename'] == u'old_test.jpg'

        # GET the image file and make sure we see the associated form.
        response = self.app.get(url('file', id=file_id), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['forms'][0]['transcription'] == u'test'
        assert resp['filename'] == u'old_test.jpg'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 100000000000
        response = self.app.get(url('file', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no file with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('file', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Now test that the restricted tag is working correctly.
        # First get the default contributor's id.
        users = h.get_users()
        contributor_id = [u for u in users if u.role == u'contributor'][0].id

        # Then add another contributor and a restricted tag.
        restricted_tag = h.generate_restricted_tag()
        my_contributor = h.generate_default_user()
        my_contributor_first_name = u'Mycontributor'
        my_contributor.first_name = my_contributor_first_name
        my_contributor.username = u'uniqueusername'
        Session.add_all([restricted_tag, my_contributor])
        Session.commit()
        my_contributor = Session.query(model.User).filter(
            model.User.first_name == my_contributor_first_name).first()
        my_contributor_id = my_contributor.id

        # Then add the default application settings with my_contributor as the
        # only unrestricted user.
        application_settings = h.generate_default_application_settings()
        application_settings.unrestricted_users = [my_contributor]
        Session.add(application_settings)
        Session.commit()

        # Finally, issue a POST request to create the restricted file with
        # the *default* contributor as the enterer.
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        extra_environ = {'test.authentication.id': contributor_id,
                         'test.application_settings': True}
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64_encoded_file': b64encode(open(wav_file_path).read()),
            'tags': [h.get_tags()[0].id]    # the restricted tag should be the only one
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restricted_file_id = resp['id']
        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted my_contributor should all be able to view the file.
        # The viewer should get a 403 error when attempting to view this file.
        # An administrator should be able to view this file.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.application_settings': True}
        response = self.app.get(url('file', id=restricted_file_id),
                        headers=self.json_headers, extra_environ=extra_environ)
        # The default contributor (qua enterer) should be able to view this file.
        extra_environ = {'test.authentication.id': contributor_id,
                         'test.application_settings': True}
        response = self.app.get(url('file', id=restricted_file_id),
                        headers=self.json_headers, extra_environ=extra_environ)
        # Mycontributor (an unrestricted user) should be able to view this
        # restricted file.
        extra_environ = {'test.authentication.id': my_contributor_id,
                         'test.application_settings': True}
        response = self.app.get(url('file', id=restricted_file_id),
                        headers=self.json_headers, extra_environ=extra_environ)
        # A (not unrestricted) viewer should *not* be able to view this file.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.application_settings': True}
        response = self.app.get(url('file', id=restricted_file_id),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        # Remove Mycontributor from the unrestricted users list and access will be denied.
        application_settings = h.get_application_settings()
        application_settings.unrestricted_users = []
        Session.add(application_settings)
        Session.commit()
        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view this restricted file.
        extra_environ = {'test.authentication.id': my_contributor_id,
                         'test.application_settings': True}
        response = self.app.get(url('file', id=restricted_file_id),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        # Remove the restricted tag from the file and the viewer should now be
        # able to view it too.
        restricted_file = Session.query(model.File).get(restricted_file_id)
        restricted_file.tags = []
        Session.add(restricted_file)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.application_settings': True}
        response = self.app.get(url('file', id=restricted_file_id),
                        headers=self.json_headers, extra_environ=extra_environ)
        assert response.content_type == 'application/json'

    @nottest
    def test_edit(self):
        """Tests that GET /files/id/edit returns a JSON object of data necessary to edit the file with id=id.

        The JSON object is of the form {'file': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Add the default application settings and the restricted tag.
        application_settings = h.generate_default_application_settings()
        restricted_tag = h.generate_restricted_tag()
        Session.add_all([restricted_tag, application_settings])
        Session.commit()
        restricted_tag = h.get_restricted_tag()
        contributor = [u for u in h.get_users() if u.role == u'contributor'][0]
        contributor_id = contributor.id

        # Create a restricted file.
        wav_file_path = os.path.join(self.test_files_path, 'old_test.wav')
        extra_environ = {'test.authentication.id': contributor_id,
                         'test.application_settings': True}
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64_encoded_file': b64encode(open(wav_file_path).read()),
            'tags': [restricted_tag.id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        self.extra_environ_admin)
        resp = json.loads(response.body)
        restricted_file_id = resp['id']

        # As a (not unrestricted) contributor, attempt to call edit on the
        # restricted form and expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.application_settings': True}
        response = self.app.get(url('edit_file', id=restricted_file_id),
                                extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_file', id=restricted_file_id), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_file', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no file with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_file', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_file', id=restricted_file_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['file']['filename'] == u'old_test.wav'
        assert response.content_type == 'application/json'

        # Valid id with GET params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetime_modified value of the
        #    store in question.

        # Add some test data to the database.
        application_settings = h.generate_default_application_settings()
        speaker = h.generate_default_speaker()
        tag = model.Tag()
        tag.name = u'name'
        Session.add_all([application_settings, speaker, tag])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'tags': h.get_mini_dicts_getter('Tag')(),
            'speakers': h.get_mini_dicts_getter('Speaker')(),
            'users': h.get_mini_dicts_getter('User')(),
            'utterance_types': h.utterance_types,
            'allowed_file_types': h.allowed_file_types
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        params = {
            # Value is a non-empty string: 'users' will be in response.
            'users': 'give me some users!',
            # Value is empty string: 'speakers' will not be in response.
            'speakers': '',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Tag.datetime_modified value: 'tags' *will* be in response.
            'tags': datetime.datetime.utcnow().isoformat(),
        }
        response = self.app.get(url('edit_file', id=restricted_file_id), params,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['data']['tags'] == data['tags']
        assert resp['data']['speakers'] == []
        assert resp['data']['users'] == data['users']
        assert resp['data']['utterance_types'] == data['utterance_types']
        assert response.content_type == 'application/json'

        # Invalid id with GET params.  It should still return 'null'.
        params = {
            # If id were valid, this would cause a speakers array to be returned
            # also.
            'speakers': 'True',
        }
        response = self.app.get(url('edit_file', id=id), params,
                            extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no file with id %s' % id in json.loads(response.body)['error']

    @nottest
    def test_serve(self):
        """Tests that GET /files/id/serve returns the file with name id from
        the permanent store, i.e., from onlinelinguisticdatabase/files/.
        """

        extra_environ_admin = {'test.authentication.role': 'administrator',
                         'test.application_settings': True}
        extra_environ_contrib = {'test.authentication.role': 'contributor',
                         'test.application_settings': True}

        # Create a restricted wav file.
        restricted_tag = h.generate_restricted_tag()
        Session.add(restricted_tag)
        Session.commit()
        restricted_tag_id = restricted_tag.id
        test_files_path = self.test_files_path
        wav_filename = u'old_test.wav'
        wav_file_path = os.path.join(test_files_path, wav_filename)
        wav_file_size = os.path.getsize(wav_file_path)
        wav_file_base64 = b64encode(open(wav_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': wav_filename,
            'base64_encoded_file': wav_file_base64,
            'tags': [restricted_tag_id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ_admin)
        resp = json.loads(response.body)
        wav_filename = resp['filename']
        wav_file_id = resp['id']

        # Retrieve the file data as the admin who entered it
        response = self.app.get(url(controller='files', action='serve', id=wav_file_id),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        response_base64 = b64encode(response.body)
        assert wav_file_base64 == response_base64
        assert guess_type(wav_filename)[0] == response.headers['Content-Type']
        assert wav_file_size == int(response.headers['Content-Length'])

        # Attempt to retrieve the file without authentication and expect to fail (401).
        response = self.app.get(url(controller='files', action='serve', id=wav_file_id),
            headers=self.json_headers, status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Attempt to retrieve the restricted file data as the contrib and expect to fail.
        response = self.app.get(url(controller='files', action='serve', id=wav_file_id),
            headers=self.json_headers, extra_environ=extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Attempt to serve an externally hosted file and expect a 400 status response.

        # Create a valid externally hosted file
        params = self.file_create_params_ext_host.copy()
        url_ = 'http://vimeo.com/54144270'
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'MIME_type': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        eh_file_id = resp['id']

        # Attempt to retrieve the externally hosted file's "data" and expect a 400 response.
        response = self.app.get(url(controller='files', action='serve', id=eh_file_id),
            headers=self.json_headers, extra_environ=extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The content of file %s is stored elsewhere at %s' % (eh_file_id, url_)
        assert response.content_type == 'application/json'

        # Request the content of a subinterval-referencing file and expect to receive
        # the file data from its parent_file

        # Create a subinterval-referencing audio file; reference the wav created above.
        params = self.file_create_params_sub_ref.copy()
        params.update({
            'parent_file': wav_file_id,
            'name': u'subinterval_x',
            'start': 1.3,
            'end': 2.6
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        sr_file_id = resp['id']

        # Retrieve the parent file's file data when requesting that of the child.
        response = self.app.get(url(controller='files', action='serve', id=sr_file_id),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        response_base64 = b64encode(response.body)
        assert wav_file_base64 == response_base64
        assert guess_type(wav_filename)[0] == response.headers['Content-Type']

        # Retrieve the reduced file data of the wav file created above.
        if self.create_reduced_size_file_copies and h.command_line_program_installed('ffmpeg'):
            response = self.app.get(url(controller='files', action='serve_reduced', id=wav_file_id),
                headers=self.json_headers, extra_environ=extra_environ_admin)
            response_base64 = b64encode(response.body)
            assert len(wav_file_base64) > len(response_base64)
            assert response.content_type == h.guess_type('x.%s' % self.preferred_lossy_audio_format)[0]
        else:
            response = self.app.get(url(controller='files', action='serve_reduced', id=wav_file_id),
                headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
            resp = json.loads(response.body)
            assert resp['error'] == u'There is no size-reduced copy of file %s' % wav_file_id
            assert response.content_type == 'application/json'

        # Retrieve the reduced file of the wav-subinterval-referencing file above
        if self.create_reduced_size_file_copies and h.command_line_program_installed('ffmpeg'):
            response = self.app.get(url(controller='files', action='serve_reduced', id=sr_file_id),
                headers=self.json_headers, extra_environ=extra_environ_admin)
            sr_response_base64 = b64encode(response.body)
            assert len(wav_file_base64) > len(sr_response_base64)
            assert sr_response_base64 == response_base64
            assert response.content_type == h.guess_type('x.%s' % self.preferred_lossy_audio_format)[0]
        else:
            response = self.app.get(url(controller='files', action='serve_reduced', id=sr_file_id),
                headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
            resp = json.loads(response.body)
            assert resp['error'] == u'There is no size-reduced copy of file %s' % sr_file_id
            assert response.content_type == 'application/json'

        # Create an image file and retrieve its contents and resized contents
        jpg_filename = u'large_image.jpg'
        jpg_file_path = os.path.join(test_files_path, jpg_filename)
        jpg_file_size = os.path.getsize(jpg_file_path)
        jpg_file_base64 = b64encode(open(jpg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': jpg_filename,
            'base64_encoded_file': jpg_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ_admin)
        resp = json.loads(response.body)
        jpg_filename = resp['filename']
        jpg_file_id = resp['id']

        # Get the image file's contents
        response = self.app.get(url(controller='files', action='serve', id=jpg_file_id),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        response_base64 = b64encode(response.body)
        assert jpg_file_base64 == response_base64
        assert guess_type(jpg_filename)[0] == response.headers['Content-Type']
        assert jpg_file_size == int(response.headers['Content-Length'])

        # Get the reduced image file's contents
        if self.create_reduced_size_file_copies and Image:
            response = self.app.get(url(controller='files', action='serve_reduced', id=jpg_file_id),
                headers=self.json_headers, extra_environ=extra_environ_admin)
            response_base64 = b64encode(response.body)
            assert jpg_file_base64 > response_base64
            assert guess_type(jpg_filename)[0] == response.headers['Content-Type']
        else:
            response = self.app.get(url(controller='files', action='serve_reduced', id=jpg_file_id),
                headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
            resp = json.loads(response.body)
            assert resp['error'] == u'There is no size-reduced copy of file %s' % jpg_file_id

        # Attempt to get the reduced contents of a file that has none (i.e., no
        # lossy_filename value) and expect to fail.

        # Create a .ogg file and retrieve its contents and fail to retrieve its resized contents
        ogg_filename = u'old_test.ogg'
        ogg_file_path = os.path.join(test_files_path, ogg_filename)
        ogg_file_size = os.path.getsize(ogg_file_path)
        ogg_file_base64 = b64encode(open(ogg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': ogg_filename,
            'base64_encoded_file': ogg_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ_admin)
        resp = json.loads(response.body)
        ogg_filename = resp['filename']
        ogg_file_id = resp['id']

        # Get the .ogg file's contents
        response = self.app.get(url(controller='files', action='serve', id=ogg_file_id),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        response_base64 = b64encode(response.body)
        assert ogg_file_base64 == response_base64
        assert guess_type(ogg_filename)[0] == response.headers['Content-Type']
        assert ogg_file_size == int(response.headers['Content-Length'])

        # Attempt to get the reduced image file's contents and expect to fail
        response = self.app.get(url(controller='files', action='serve_reduced', id=ogg_file_id),
            headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no size-reduced copy of file %s' % ogg_file_id

        # Invalid id
        response = self.app.get(url(controller='files', action='serve', id=123456789012),
            headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no file with id 123456789012'

    @nottest
    def test_file_reduction(self):
        """Verifies that reduced-size copies of image and wav files are created in files/reduced_files
        and that the names of these reduced-size files is returned as the lossy_filename
        attribute.

        Note that this test will fail if create_reduced_size_file_copies is set
        to 0 in the config file.
        """
        def get_size(path):
            return os.stat(path).st_size

        # Create a JPG file that will not be reduced because it is already small enough
        jpg_file_path = os.path.join(self.test_files_path, 'old_test.jpg')
        jpg_file_size = os.path.getsize(jpg_file_path)
        jpg_file_base64 = b64encode(open(jpg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64_encoded_file': jpg_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = Session.query(model.File).count()
        assert resp['filename'] == u'old_test.jpg'
        assert resp['MIME_type'] == u'image/jpeg'
        assert resp['size'] == jpg_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert resp['lossy_filename'] == None
        assert file_count == 1
        assert len(os.listdir(self.reduced_files_path)) == 0

        # Create a large JPEG file and expect a reduced-size .jpg to be created in
        # files/reduced_files.
        filename = u'large_image.jpg'
        jpg_file_path = os.path.join(self.test_files_path, filename)
        jpg_reduced_file_path = os.path.join(self.reduced_files_path, filename)
        jpg_file_base64 = b64encode(open(jpg_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': filename,
            'base64_encoded_file': jpg_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        new_file_count = Session.query(model.File).count()
        assert new_file_count == file_count + 1
        assert resp['filename'] == filename
        assert resp['MIME_type'] == u'image/jpeg'
        assert resp['enterer']['first_name'] == u'Admin'
        if self.create_reduced_size_file_copies and Image:
            assert resp['lossy_filename'] == filename
            assert resp['lossy_filename'] in os.listdir(self.reduced_files_path)
            assert get_size(jpg_file_path) > get_size(jpg_reduced_file_path)
        else:
            assert resp['lossy_filename'] is None
            assert not os.path.isfile(jpg_reduced_file_path)

        # Create a large GIF file and expect a reduced-size .gif to be created in
        # files/reduced_files.
        filename = u'large_image.gif'
        gif_file_path = os.path.join(self.test_files_path, filename)
        gif_reduced_file_path = os.path.join(self.reduced_files_path, filename)
        gif_file_base64 = b64encode(open(gif_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': filename,
            'base64_encoded_file': gif_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = new_file_count
        new_file_count = Session.query(model.File).count()
        assert new_file_count == file_count + 1
        assert resp['filename'] == filename
        assert resp['MIME_type'] == u'image/gif'
        assert resp['enterer']['first_name'] == u'Admin'
        if self.create_reduced_size_file_copies and Image:
            assert resp['lossy_filename'] == filename
            assert resp['lossy_filename'] in os.listdir(self.reduced_files_path)
            assert get_size(gif_file_path) > get_size(gif_reduced_file_path)
        else:
            assert resp['lossy_filename'] is None
            assert not os.path.isfile(gif_reduced_file_path)

        # Create a large PNG file and expect a reduced-size .png to be created in
        # files/reduced_files.
        filename = 'large_image.png'
        png_file_path = os.path.join(self.test_files_path, filename)
        png_reduced_file_path = os.path.join(self.reduced_files_path, filename)
        params = self.file_create_params_MPFD.copy()
        params.update({'filename': filename})
        response = self.app.post(url('/files'), params,
                                 extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', png_file_path)])
        resp = json.loads(response.body)
        file_count = new_file_count
        new_file_count = Session.query(model.File).count()
        assert new_file_count == file_count + 1
        assert resp['filename'] == filename
        assert resp['MIME_type'] == u'image/png'
        assert resp['enterer']['first_name'] == u'Admin'
        if self.create_reduced_size_file_copies and Image:
            assert resp['lossy_filename'] == filename
            assert resp['lossy_filename'] in os.listdir(self.reduced_files_path)
            assert get_size(png_file_path) > get_size(png_reduced_file_path)
        else:
            assert resp['lossy_filename'] is None
            assert not os.path.isfile(png_reduced_file_path)

        # Test copying .wav files to .ogg/.mp3

        format_ = self.preferred_lossy_audio_format

        # Create a WAV file for which an .ogg/.mp3 Vorbis copy will be created in
        # files/reduced_files.
        filename = 'old_test.wav'
        lossy_filename = u'%s.%s' % (os.path.splitext(filename)[0], format_)
        lossy_file_path = os.path.join(self.reduced_files_path, lossy_filename)
        wav_file_path = os.path.join(self.test_files_path, filename)
        wav_file_size = os.path.getsize(wav_file_path)
        wav_file_base64 = b64encode(open(wav_file_path).read())
        params = self.file_create_params_base64.copy()
        params.update({
            'filename': filename,
            'base64_encoded_file': wav_file_base64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        file_count = new_file_count
        new_file_count = Session.query(model.File).count()
        assert resp['filename'] == filename
        assert resp['MIME_type'] == u'audio/x-wav'
        assert resp['size'] == wav_file_size
        assert resp['enterer']['first_name'] == u'Admin'
        assert new_file_count == file_count + 1
        if self.create_reduced_size_file_copies and h.command_line_program_installed('ffmpeg'):
            assert resp['lossy_filename'] == lossy_filename
            assert resp['lossy_filename'] in os.listdir(self.reduced_files_path)
            assert get_size(wav_file_path) > get_size(lossy_file_path)
        else:
            assert resp['lossy_filename'] is None
            assert not os.path.isfile(lossy_file_path)

    @nottest
    def test_new_search(self):
        """Tests that GET /files/new_search returns the search parameters for searching the files resource."""
        query_builder = SQLAQueryBuilder('File')
        response = self.app.get(url('/files/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['search_parameters'] == h.get_search_parameters(query_builder)
