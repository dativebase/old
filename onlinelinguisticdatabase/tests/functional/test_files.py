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
from paste.deploy import appconfig
from mimetypes import guess_type
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
from pylons import config
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from paste.deploy.converters import asbool

try:
    import Image
except ImportError:
    Image = None

log = logging.getLogger(__name__)

class TestFilesController(TestController):

    config = appconfig('config:test.ini', relative_to='.')
    create_reduced_size_file_copies = asbool(config.get('create_reduced_size_file_copies', False))
    preferred_lossy_audio_format = config.get('preferred_lossy_audio_format', 'ogg')
    here = config['here']
    filesPath = os.path.join(here, u'files')
    reducedFilesPath = os.path.join(filesPath, u'reduced_files')
    testFilesPath = os.path.join(here, 'test_files')

    createParams = {
        'filename': u'',        # Will be filtered out on update requests
        'description': u'',
        'dateElicited': u'',    # mm/dd/yyyy
        'elicitor': u'',
        'speaker': u'',
        'utteranceType': u'',
        'tags': [],
        'forms': [],
        'base64EncodedFile': '' # file data Base64 encoded; will be filtered out on update requests
    }

    # Empty create dict for multipart/form-data file creation requests.  Will be
    # converted to a conventional POST k=v body format.  'tags-i' and 'forms-i' for
    # i > 0 can be added.
    createParamsBasic = {
        'filename': u'',        # Will be filtered out on update requests
        'description': u'',
        'dateElicited': u'',    # mm/dd/yyyy
        'elicitor': u'',
        'speaker': u'',
        'utteranceType': u'',
        'tags-0': u'',
        'forms-0': u''
    }

    # Empty create dict for subinterval-referencing file creation requests
    createParamsSR = {
        'parentFile': u'',
        'name': u'',
        'start': u'',
        'end': u'',
        'description': u'',
        'dateElicited': u'',    # mm/dd/yyyy
        'elicitor': u'',
        'speaker': u'',
        'utteranceType': u'',
        'tags': [],
        'forms': []
    }

    # Empty create dict for externally hosted file creation requests
    createParamsEH = {
        'url': u'',
        'name': u'',
        'password': u'',
        'MIMEtype': u'',
        'description': u'',
        'dateElicited': u'',    # mm/dd/yyyy
        'elicitor': u'',
        'speaker': u'',
        'utteranceType': u'',
        'tags': [],
        'forms': []
    }

    createFormParams = {
        'transcription': u'',
        'phoneticTranscription': u'',
        'narrowPhoneticTranscription': u'',
        'morphemeBreak': u'',
        'grammaticality': u'',
        'morphemeGloss': u'',
        'translations': [{'transcription': u'', 'grammaticality': u''}],
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
        'dateElicited': u'',     # mm/dd/yyyy
        'files': []
    }

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_view = {'test.authentication.role': u'viewer'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language, recreate the default
    # users and clear the files directory.
    def tearDown(self):
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()
        h.clearDirectoryOfFiles(self.filesPath)
        h.clearDirectoryOfFiles(self.reducedFilesPath)

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        response = self.app.get(url('forms'), extra_environ=extra_environ)

    #@nottest
    def test_index(self):
        """Tests that GET /files returns a JSON array of files with expected values."""
        # Test that the restricted tag is working correctly.
        # First get the users.
        users = h.getUsers()
        administratorId = [u for u in users if u.role == u'administrator'][0].id
        contributorId = [u for u in users if u.role == u'contributor'][0].id
        viewerId = [u for u in users if u.role == u'viewer'][0].id

        # Then add a contributor and a restricted tag.
        restrictedTag = h.generateRestrictedTag()
        myContributor = h.generateDefaultUser()
        myContributorFirstName = u'Mycontributor'
        myContributor.firstName = myContributorFirstName
        Session.add_all([restrictedTag, myContributor])
        Session.commit()
        myContributor = Session.query(model.User).filter(
            model.User.firstName == myContributorFirstName).first()
        myContributorId = myContributor.id
        restrictedTag = h.getRestrictedTag()

        # Then add the default application settings with myContributor as the
        # only unrestricted user.
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.unrestrictedUsers = [myContributor]
        Session.add(applicationSettings)
        Session.commit()

        # Finally, issue two POST requests to create two default files with the
        # *default* contributor as the enterer.  One file will be restricted and
        # the other will not be.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}

        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        wavFileBase64Encoded = b64encode(open(wavFilePath).read())

        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64Encoded = b64encode(open(jpgFilePath).read())

        # Create the restricted file.
        params = self.createParams.copy()
        params.update({
            'filename': u'test_restricted_file.wav',
            'base64EncodedFile': wavFileBase64Encoded,
            'tags': [h.getTags()[0].id]    # the restricted tag should be the only one
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restrictedFileId = resp['id']

        # Create the unrestricted file.
        params = self.createParams.copy()
        params.update({
            'filename': u'test_unrestricted_file.jpg',
            'base64EncodedFile': jpgFileBase64Encoded
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        unrestrictedFileId = resp['id']

        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted myContributor should all be able to view both files.
        # The viewer will only receive the unrestricted file.

        # An administrator should be able to view both files.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert resp[0]['filename'] == u'test_restricted_file.wav'
        assert resp[1]['filename'] == u'test_unrestricted_file.jpg'
        assert response.content_type == 'application/json'

        # The default contributor (qua enterer) should also be able to view both
        # files.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Mycontributor (an unrestricted user) should also be able to view both
        # files.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # A (not unrestricted) viewer should be able to view only one file.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove Mycontributor from the unrestricted users list and access to
        # the second file will be denied.
        applicationSettings = h.getApplicationSettings()
        applicationSettings.unrestrictedUsers = []
        Session.add(applicationSettings)
        Session.commit()

        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view the restricted file.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True,
                         'test.retainApplicationSettings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove the restricted tag from the file and the viewer should now be
        # able to view it too.
        restrictedFile = Session.query(model.File).get(restrictedFileId)
        restrictedFile.tags = []
        Session.add(restrictedFile)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Clear all Files (actually, everything but the tags, users and languages)
        h.clearAllModels(['User', 'Tag', 'Language'])

        # Now add 100 files.  The even ones will be restricted, the odd ones not.
        # These files will be deficient, i.e., have no binary data or MIMEtype
        # but that's ok ...
        def createFileFromIndex(index):
            file = model.File()
            file.filename = u'name_%d.jpg' % index
            return file
        files = [createFileFromIndex(i) for i in range(1, 101)]
        Session.add_all(files)
        Session.commit()
        files = h.getFiles()
        restrictedTag = h.getRestrictedTag()
        for file in files:
            if int(file.filename.split('_')[1].split('.')[0]) % 2 == 0:
                file.tags.append(restrictedTag)
            Session.add(file)
        Session.commit()
        files = h.getFiles()    # ordered by File.id ascending

        # An administrator should be able to retrieve all of the files.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['filename'] == u'name_1.jpg'
        assert resp[0]['id'] == files[0].id

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['filename'] == files[46].filename

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'File', 'orderByAttribute': 'filename',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('files'), orderByParams,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        resultSet = sorted([f.filename for f in files], reverse=True)
        assert resultSet == [f['filename'] for f in resp]
        assert response.content_type == 'application/json'

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'File', 'orderByAttribute': 'filename',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('files'), params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['filename']

        # The default viewer should only be able to see the odd numbered files,
        # even with a paginator.
        itemsPerPage = 7
        page = 7
        paginator = {'itemsPerPage': itemsPerPage, 'page': page}
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == itemsPerPage
        assert resp['items'][0]['filename'] == u'name_%d.jpg' % (
            ((itemsPerPage * (page - 1)) * 2) + 1)

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'File', 'orderByAttribute': 'filename',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('files'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"

        # Expect the default BY id ASCENDING ordering when the orderByModel/Attribute
        # param is invalid.
        orderByParams = {'orderByModel': 'Fileage', 'orderByAttribute': 'nom',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('files'), orderByParams,
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp[0]['id'] == files[0].id

        # Expect a 400 error when the paginator GET params are empty, not
        # specified or integers that are less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'
        assert response.content_type == 'application/json'

    #@nottest
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
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64EncodedFile': b64encode(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert resp['filename'] == u'old_test.wav'
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 1
        assert response.content_type == 'application/json'

        # Create a test image file.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = b64encode(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        fileId = anImageId = resp['id']
        assert resp['filename'] == u'old_test.jpg'
        assert resp['MIMEtype'] == u'image/jpeg'
        assert resp['size'] == jpgFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 2

        # Create a test image file with many-to-many relations, i.e., tags and
        # forms.  First create a couple of tags.
        tag1 = model.Tag()
        tag1.name = u'tag 1'
        tag2 = model.Tag()
        tag2.name = u'tag 2'
        restrictedTag = h.generateRestrictedTag()
        Session.add_all([tag1, tag2, restrictedTag])
        Session.commit()
        tag1Id = tag1.id
        tag2Id = tag2.id
        restrictedTagId = restrictedTag.id

        # Then create a form to associate.
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'test',
            'translations': [{'transcription': u'test', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formId = resp['id']

        # Now create the file with forms and tags
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64,
            'tags': [tag1Id, tag2Id],
            'forms': [formId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        fileId = resp['id']
        assert resp['filename'][:9] == u'old_test_'
        assert resp['MIMEtype'] == u'image/jpeg'
        assert resp['size'] == jpgFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert sorted([t['id'] for t in resp['tags']]) == sorted([tag1Id, tag2Id])
        assert resp['forms'][0]['transcription'] == u'test'
        assert fileCount == 3

        # Invalid input
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createParams.copy()
        params.update({
            'filename': u'',                    # empty; not allowed
            'base64EncodedFile': '',        # empty; not allowed
            'utteranceType': u'l' * 1000,   # too long
            'dateElicited': '31/12/2012',   # wrong format
            'speaker': 200                  # invalid id
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert u'Value must be one of: None; Object Language Utterance; Metalanguage Utterance; Mixed Utterance' in \
            resp['errors']['utteranceType']
        assert resp['errors']['speaker'] == u'There is no speaker with id 200.'
        assert resp['errors']['dateElicited'] == u'Please enter a month from 1 to 12'
        assert resp['errors']['filename'] == u'Please enter a value'
        assert resp['errors']['base64EncodedFile']== u'Please enter a value'
        assert fileCount == 3
        assert response.content_type == 'application/json'

        # Create an audio file with unicode characters.  Show that spaces are
        # replaced with underscores and that apostrophes and quotation marks are
        # removed.
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createParams.copy()
        params.update({
            'filename': u'\u201Cold te\u0301st\u201D.wav',
            'base64EncodedFile': b64encode(open(wavFilePath).read()),
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        aWavFileId = resp['id']
        fileCount = Session.query(model.File).count()
        assert u'\u201Cold_te\u0301st\u201D.wav' in os.listdir(self.filesPath)
        assert resp['filename'] == u'\u201Cold_te\u0301st\u201D.wav'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 4
        assert restrictedTagId in [t['id'] for t in resp['tags']]
        assert response.content_type == 'application/json'

        # Attempt to create an illicit file type (.html) but with a valid
        # extension (.wav).  Expect an error, i.e., validation detects that the
        # file is really html, despite the misleading extension.
        filesDirList = os.listdir(self.filesPath)
        htmlFilePath = os.path.join(self.testFilesPath, 'illicit.html')
        htmlFileBase64 = b64encode(open(htmlFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': u'pretend_its_wav.wav',
            'base64EncodedFile': htmlFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        newFilesDirList = os.listdir(self.filesPath)
        assert fileCount == 4
        assert resp['errors'] == u"The file extension does not match the file's true type (audio/x-wav vs. text/html, respectively)."
        assert filesDirList == newFilesDirList

        ########################################################################
        # multipart/form-data file creation
        ########################################################################

        # Upload a file using the multipart/form-data Content-Type and a POST
        # request to /files.  Here we do not supply a filename POST param so the
        # files controller creates one based on the path automatically included
        # in filedata.  The controller removes the path separators of its os
        # when it creates the filename; however path separators from a foreign os
        # may remain in the generated filename.
        params = self.createParamsBasic.copy()
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', wavFilePath)])
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert resp['filename'] in os.listdir(self.filesPath)
        assert resp['filename'][:8] == u'old_test'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 5
        assert response.content_type == 'application/json'

        # Upload a file using the multipart/form-data Content-Type and a POST
        # request to /files.  Here we do supply a filename and some metadata.
        params = self.createParamsBasic.copy()
        params.update({
            'filename': u'wavfile.wav',
            'description': u'multipart/form-data',
            'dateElicited': u'12/03/2011',    # mm/dd/yyyy
            'utteranceType': u'Mixed Utterance',
            'tags-0': tag1Id,
            'tags-1': tag2Id,
            'forms-0': formId
        })
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', wavFilePath)])
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert u'wavfile.wav' in os.listdir(self.filesPath)
        assert resp['filename'] == u'wavfile.wav'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert sorted([t['id'] for t in resp['tags']]) == sorted([tag1Id, tag2Id])
        assert resp['forms'][0]['id'] == formId
        assert resp['utteranceType'] == u'Mixed Utterance'
        assert resp['description'] == u'multipart/form-data'
        assert resp['dateElicited'] == u'2011-12-03'
        assert fileCount == 6
        assert response.content_type == 'application/json'

        # Upload using multipart/form-data and attempt to pass a malicious
        # filename; the path separator should be removed from the filename.  If
        # the separator were not removed, this filename could cause the file to
        # be written to the parent directory of the files directory
        params = self.createParamsBasic.copy()
        params.update({'filename': u'../wavfile.wav'})
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
            upload_files=[('filedata', wavFilePath)])
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        binaryFilesList = os.listdir(self.filesPath)
        binaryFilesListCount = len(binaryFilesList)
        assert u'..wavfile.wav' in binaryFilesList
        assert resp['filename'] == u'..wavfile.wav'
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 7
        assert response.content_type == 'application/json'

        # Upload using multipart/form-data and attempt to pass an invalid file
        # type (.html) but with a valid extension (.wav).  Expect an error.
        htmlFilePath = os.path.join(self.testFilesPath, 'illicit.html')
        filesDirList = os.listdir(self.filesPath)
        params = self.createParamsBasic.copy()
        params.update({'filename': u'pretend_its_wav.wav'})
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
            upload_files=[('filedata', htmlFilePath)], status=400)
        resp = json.loads(response.body)
        newFileCount = Session.query(model.File).count()
        newFilesDirList = os.listdir(self.filesPath)
        assert fileCount == newFileCount
        assert resp['errors'] == u"The file extension does not match the file's true type (audio/x-wav vs. text/html, respectively)."
        assert filesDirList == newFilesDirList

        # Try the same as above but instead of providing a deceitful filename in
        # the POST params, upload a file with a false extension.
        htmlFilePath = os.path.join(self.testFilesPath, 'illicit.wav')
        filesDirList = newFilesDirList
        params = self.createParamsBasic.copy()
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
            upload_files=[('filedata', htmlFilePath)], status=400)
        resp = json.loads(response.body)
        newFileCount = Session.query(model.File).count()
        newFilesDirList = os.listdir(self.filesPath)
        assert fileCount == newFileCount
        assert resp['errors'] == u"The file extension does not match the file's true type (audio/x-wav vs. text/html, respectively)."
        assert filesDirList == newFilesDirList

        ########################################################################
        # Subinterval-Referencing File
        ########################################################################

        # Create a subinterval-referencing audio file; reference one of the wav
        # files created earlier.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': aWavFileId,
            'name': u'subinterval_x',
            'start': 1.3,
            'end': 2.6
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        newBinaryFilesList = os.listdir(self.filesPath)
        newBinaryFilesListCount = len(newBinaryFilesList)
        subintervalReferencingId = resp['id']
        x = Session.query(model.File).get(subintervalReferencingId)
        assert newBinaryFilesListCount == binaryFilesListCount
        assert u'\u201Cold_te\u0301st\u201D.wav' in newBinaryFilesList
        assert u'subinterval_x' not in newBinaryFilesList
        assert resp['filename'] == None
        assert resp['parentFile']['filename'] == u'\u201Cold_te\u0301st\u201D.wav'
        assert resp['name'] == u'subinterval_x'
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == None
        assert resp['parentFile']['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['start'] == 1.3
        assert type(resp['start']) is float
        assert resp['end'] == 2.6
        assert type(resp['end']) is float
        assert fileCount == 8
        assert response.content_type == 'application/json'

        # Attempt to create another subinterval-referencing audio file; fail
        # because name is too long, parentFile is empty, start is not a number
        # and end is unspecified
        params = self.createParamsSR.copy()
        params.update({
            'name': u'subinterval_x' * 200,
            'start': u'a',
            'end': None
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert fileCount == 8   # unchanged
        assert resp['errors']['parentFile'] == u'An id corresponding to an existing audio or video file must be provided.'
        assert resp['errors']['start'] == u'Please enter a number'
        assert resp['errors']['end'] == u'Please enter a value'
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'

        # Attempt to create another subinterval-referencing audio file; fail
        # because the contributor is not authorized to access the restricted parentFile.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': aWavFileId,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_contrib, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert fileCount == 8
        assert resp['errors']['parentFile'] == u'You are not authorized to access the file with id %d.' % aWavFileId

        # Create another subinterval-referencing audio file; this one's parent is
        # restricted.  Note that it does not itself become restricted.  Note also
        # that a name is not required.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': aWavFileId,
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert fileCount == 9
        assert resp['parentFile']['id'] == aWavFileId
        assert u'restricted' not in [t['name'] for t in resp['tags']]
        assert resp['name'] == resp['parentFile']['name']

        # Attempt to create another subinterval-referencing file; fail because
        # the parent file is not an A/V file.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': anImageId,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert fileCount == 9
        assert resp['errors']['parentFile'] == u'File %d is not an audio or a video file.' % anImageId

        # Attempt to create another subinterval-referencing file; fail because
        # the parent file id is invalid
        badId = 1000009252345345
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': badId,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert fileCount == 9
        assert resp['errors']['parentFile'] == u'There is no file with id %d.' % badId

        # Attempt to create another subinterval-referencing file; fail because
        # the parent file id is itself a subinterval-referencing file
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': subintervalReferencingId,
            'name': u'subinterval_y',
            'start': 3.75,
            'end': 4.999
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert fileCount == 9
        assert resp['errors']['parentFile'] == u'The parent file cannot itself be a subinterval-referencing file.'

        # Attempt to create a subinterval-referencing audio file; fail because
        # start >= end.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': aWavFileId,
            'name': u'subinterval_z',
            'start': 1.3,
            'end': 1.3
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert response.content_type == 'application/json'
        assert resp['errors'] == u'The start value must be less than the end value.'

        ########################################################################
        # externally hosted file creation
        ########################################################################

        # Create a valid externally hosted file
        params = self.createParamsEH.copy()
        url_ = 'http://vimeo.com/54144270'
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'MIMEtype': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['description'] == u'A large video file I didn\'t want to upload here.'
        assert resp['url'] == url_

        # Attempt to create an externally hosted file with invalid params
        params = self.createParamsEH.copy()
        url_ = 'http://vimeo/541442705414427054144270541442705414427054144270'  # Invalid url
        params.update({
            'url': url_,
            'name': u'invalid externally hosted file',
            'MIMEtype': u'video/gepm',      # invalid MIMEtype
            'description': u'A large video file, sadly invalid.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['MIMEtype'] == u'The file upload failed because the file type video/gepm is not allowed.'
        resp['errors']['url'] == u'You must provide a full domain name (like vimeo.com)'

        # Attempt to create an externally hosted file with different invalid params
        params = self.createParamsEH.copy()
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
        params = self.createParamsEH.copy()
        url_ = 'http://vimeo.com/54144270'
        params.update({
            'url': url_,
            'MIMEtype': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u''

    #@nottest
    def test_relational_restrictions(self):
        """Tests that the restricted tag works correctly with respect to relational attributes of files.

        That is, tests that (a) file.forms does not return restricted forms to
        restricted users and (b) a restricted user cannot append a restricted
        form to file.forms."""

        admin = self.extra_environ_admin.copy()
        admin.update({'test.applicationSettings': True})
        contrib = self.extra_environ_contrib.copy()
        contrib.update({'test.applicationSettings': True})

        # Create a test audio file.
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64EncodedFile': b64encode(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert resp['filename'] == u'old_test.wav'
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 1
        assert response.content_type == 'application/json'

        # First create the restricted tag.
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTagId = restrictedTag.id

        # Then create two forms, one restricted and one not.
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'restricted',
            'translations': [{'transcription': u'restricted', 'grammaticality': u''}],
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 admin)
        resp = json.loads(response.body)
        restrictedFormId = resp['id']

        params = self.createFormParams.copy()
        params.update({
            'transcription': u'unrestricted',
            'translations': [{'transcription': u'unrestricted', 'grammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 admin)
        resp = json.loads(response.body)
        unrestrictedFormId = resp['id']

        # Now, as a (restricted) contributor, attempt to create a file and
        # associate it to a restricted form -- expect to fail.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = b64encode(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64,
            'forms': [restrictedFormId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the form with id %d.' % restrictedFormId in \
            resp['errors']['forms']

        # Now, as a (restricted) contributor, attempt to create a file and
        # associate it to an unrestricted form -- expect to succeed.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = b64encode(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64,
            'forms': [unrestrictedFormId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 contrib)
        resp = json.loads(response.body)
        unrestrictedFileId = resp['id']
        assert resp['filename'] == u'old_test.jpg'
        assert resp['forms'][0]['transcription'] == u'unrestricted'

        # Now, as a(n unrestricted) administrator, attempt to create a file and
        # associate it to a restricted form -- expect (a) to succeed and (b) to
        # find that the file is now restricted.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = b64encode(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64,
            'forms': [restrictedFormId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        indirectlyRestrictedFileId = resp['id']
        assert resp['filename'][:8] == u'old_test'
        assert resp['forms'][0]['transcription'] == u'restricted'
        assert u'restricted' in [t['name'] for t in resp['tags']]

        # Now show that the indirectly restricted files are inaccessible to
        # unrestricted users.
        response = self.app.get(url('files'), headers=self.json_headers,
                                extra_environ=contrib)
        resp = json.loads(response.body)
        assert indirectlyRestrictedFileId not in [f['id'] for f in resp]

        # Now, as a(n unrestricted) administrator, create a file.
        unrestrictedFileParams = self.createParams.copy()
        unrestrictedFileParams.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64
        })
        params = json.dumps(unrestrictedFileParams)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        unrestrictedFileId = resp['id']
        assert resp['filename'][:8] == u'old_test'
        assert response.content_type == 'application/json'

        # As a restricted contributor, attempt to update the unrestricted file
        # just created by associating it to a restricted form -- expect to fail.
        unrestrictedFileParams.update({'forms': [restrictedFormId]})
        params = json.dumps(unrestrictedFileParams)
        response = self.app.put(url('file', id=unrestrictedFileId), params,
                                self.json_headers, contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the form with id %d.' % restrictedFormId in \
            resp['errors']['forms']
        assert response.content_type == 'application/json'

        # As an unrestricted administrator, attempt to update an unrestricted file
        # by associating it to a restricted form -- expect to succeed.
        response = self.app.put(url('file', id=unrestrictedFileId), params,
                                self.json_headers, admin)
        resp = json.loads(response.body)
        assert resp['id'] == unrestrictedFileId
        assert u'restricted' in [t['name'] for t in resp['tags']]

        # Now show that the newly indirectly restricted file is also
        # inaccessible to an unrestricted user.
        response = self.app.get(url('file', id=unrestrictedFileId),
                headers=self.json_headers, extra_environ=contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

    #@nottest
    def test_create_large(self):
        """Tests that POST /files correctly creates a large file.

        WARNING 1: long-running test.

        WARNING: 2: if a large file named old_test_long.wav does not exist in
        test_files, this test will pass vacuously.  I don't want to include such
        a large file in the code base so this file needs to be created if one
        wants this test to run.
        """

        fileCount = newFileCount = Session.query(model.File).count()

        # Try to create a file with a > 20 MB file as content using JSON/Base64
        # encoding and expect to fail because the file is too big.
        longWavFileName = 'old_test_long.wav'
        longWavFilePath = os.path.join(self.testFilesPath, longWavFileName)
        if os.path.exists(longWavFilePath):
            longWavFileSize = os.path.getsize(longWavFilePath)
            params = self.createParams.copy()
            params.update({
                'filename': longWavFileName,
                'base64EncodedFile': b64encode(open(longWavFilePath).read())
            })
            params = json.dumps(params)
            response = self.app.post(url('files'), params, self.json_headers,
                                     self.extra_environ_admin, status=400)
            resp = json.loads(response.body)
            newFileCount = Session.query(model.File).count()
            assert fileCount == newFileCount
            assert resp['error'] == u'The request body is too large; use the multipart/form-data Content-Type when uploading files greater than 20MB.'
            assert response.content_type == 'application/json'

        # Try to create a file with a ~6MB .wav file as content using JSON/Base64
        # encoding and expect to succeed because the file is < 20MB.
        mediumWavFileName = u'old_test_medium.wav'
        mediumWavFilePath = os.path.join(self.testFilesPath, mediumWavFileName)
        if os.path.exists(mediumWavFilePath):
            oldReducedDirList = os.listdir(self.reducedFilesPath)
            mediumWavFileSize = os.path.getsize(mediumWavFilePath)
            params = self.createParams.copy()
            params.update({
                'filename': mediumWavFileName,
                'base64EncodedFile': b64encode(open(mediumWavFilePath).read())
            })
            params = json.dumps(params)
            response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
            resp = json.loads(response.body)
            fileCount = newFileCount
            newFileCount = Session.query(model.File).count()
            newReducedDirList = os.listdir(self.reducedFilesPath)
            lossyFilename = '%s.%s' % (os.path.splitext(mediumWavFileName)[0],
                                       self.config.get('preferred_lossy_audio_format', 'ogg'))
            assert fileCount + 1 == newFileCount
            assert resp['filename'] == mediumWavFileName
            assert resp['MIMEtype'] == u'audio/x-wav'
            assert resp['size'] == mediumWavFileSize
            assert resp['enterer']['firstName'] == u'Admin'
            assert response.content_type == 'application/json'
            assert lossyFilename not in oldReducedDirList
            if self.create_reduced_size_file_copies and h.commandLineProgramInstalled(['ffmpeg']):
                assert resp['lossyFilename'] == lossyFilename
                assert lossyFilename in newReducedDirList
            else:
                assert resp['lossyFilename'] == None
                assert lossyFilename not in newReducedDirList

        # Create the large (> 20MB) .wav file from above using the multipart/form-data
        # POST method.
        if os.path.exists(longWavFilePath):
            longWavFileSize = os.path.getsize(longWavFilePath)
            params = self.createParamsBasic.copy()
            params.update({'filename': longWavFileName})
            response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', longWavFilePath)])
            resp = json.loads(response.body)
            fileCount = newFileCount
            newFileCount = Session.query(model.File).count()
            newReducedDirList = os.listdir(self.reducedFilesPath)
            lossyFilename = '%s.%s' % (os.path.splitext(longWavFileName)[0],
                                       self.config.get('preferred_lossy_audio_format', 'ogg'))
            assert fileCount + 1 == newFileCount
            assert resp['filename'] == longWavFileName
            assert resp['MIMEtype'] == u'audio/x-wav'
            assert resp['size'] == longWavFileSize
            assert resp['enterer']['firstName'] == u'Admin'
            assert response.content_type == 'application/json'
            assert lossyFilename not in oldReducedDirList
            if self.create_reduced_size_file_copies and h.commandLineProgramInstalled(['ffmpeg']):
                assert resp['lossyFilename'] == lossyFilename
                assert lossyFilename in newReducedDirList
            else:
                assert resp['lossyFilename'] == None
                assert lossyFilename not in newReducedDirList
    #@nottest
    def test_new(self):
        """Tests that GET /file/new returns an appropriate JSON object for creating a new OLD file.

        The properties of the JSON object are 'tags', 'utteranceTypes',
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
        applicationSettings = h.generateDefaultApplicationSettings()
        restrictedTag = h.generateRestrictedTag()
        speaker = h.generateDefaultSpeaker()
        Session.add_all([applicationSettings, restrictedTag, speaker])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'tags': h.getMiniDictsGetter('Tag')(),
            'speakers': h.getMiniDictsGetter('Speaker')(),
            'users': h.getMiniDictsGetter('User')(),
            'utteranceTypes': h.utteranceTypes,
            'allowedFileTypes': h.allowedFileTypes
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
        assert resp['utteranceTypes'] == data['utteranceTypes']
        assert resp['allowedFileTypes'] == data['allowedFileTypes']
        assert response.content_type == 'application/json'

        # GET /new_file with params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetimeModified value of the
        #    store in question.
        params = {
            # Value is any string: 'speakers' will be in response.
            'speakers': 'anything can go here!',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent User.datetimeModified value: 'users' *will* be in
            # response.
            'users': datetime.datetime.utcnow().isoformat(),
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent Tag.datetimeModified value: 'tags' will *not* be in response.
            'tags': h.getMostRecentModificationDatetime('Tag').isoformat()
        }
        response = self.app.get(url('new_file'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['tags'] == []
        assert resp['speakers'] == data['speakers']
        assert resp['users'] == data['users']
        assert resp['utteranceTypes'] == data['utteranceTypes']
        assert response.content_type == 'application/json'

    #@nottest
    def test_update(self):
        """Tests that PUT /files/id correctly updates an existing file."""

        fileCount = Session.query(model.File).count()

        # Add the default application settings and the restricted tag.
        restrictedTag = h.generateRestrictedTag()
        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add_all([applicationSettings, restrictedTag])
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        restrictedTagId = restrictedTag.id

        # Create a file to update.
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createParams.copy()
        originalName = u'test_update_name.wav'
        params.update({
            'filename': originalName,
            'tags': [restrictedTag.id],
            'description': u'description',
            'base64EncodedFile': b64encode(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        id = int(resp['id'])
        newFileCount = Session.query(model.File).count()
        assert resp['filename'] == originalName
        assert newFileCount == fileCount + 1

        # As a viewer, attempt to update the restricted file we just created.
        # Expect to fail.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
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
        params = self.createParams.copy()
        params.update({
            'description': u'A file that has been updated.'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=id), params,
                                self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newFileCount = Session.query(model.File).count()
        assert resp['description'] == u'A file that has been updated.'
        assert resp['tags'] == []
        assert newFileCount == fileCount + 1
        assert response.content_type == 'application/json'

        # Attempt an update with no new data.  Expect a 400 error
        # and response['errors'] = {'no change': The update request failed
        # because the submitted data were not new.'}.
        response = self.app.put(url('file', id=id), params, self.json_headers,
                                self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'the submitted data were not new' in resp['error']

        # Add a speaker and some tags to the db.
        speaker = h.generateDefaultSpeaker()
        tag1 = model.Tag()
        tag1.name = u'tag 1'
        tag2 = model.Tag()
        tag2.name = u'tag 2'
        Session.add_all([speaker, tag1, tag2])
        Session.commit()
        speaker = h.getSpeakers()[0]
        tag1Id = tag1.id
        tag2Id = tag2.id
        speakerId = speaker.id

        # Now update our file by adding a many-to-one datum, viz. a speaker
        params = self.createParams.copy()
        params.update({'speaker': speaker.id})
        params = json.dumps(params)
        response = self.app.put(url('file', id=id), params, self.json_headers,
                                 extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['speaker']['firstName'] == speaker.firstName

        # Finally, update the file by adding some many-to-many data, i.e., tags
        params = self.createParams.copy()
        params.update({'tags': [tag1Id, tag2Id]})
        params = json.dumps(params)
        response = self.app.put(url('file', id=id), params, self.json_headers,
                                 extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert sorted([t['name'] for t in resp['tags']]) == [u'tag 1', u'tag 2']

        ########################################################################
        # Updating "Plain Files"
        ########################################################################

        # Create a file using the multipart/form-data POST method.
        params = self.createParamsBasic.copy()
        params.update({'filename': u'multipart.wav'})
        response = self.app.post(url('/files'), params, extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', wavFilePath)])
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        plainFileId = resp['id']
        assert resp['filename'] == u'multipart.wav'
        assert resp['filename'] in os.listdir(self.filesPath)
        assert resp['name'] == resp['filename']     # name value set in files controller, user can't change this
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['enterer']['firstName'] == u'Admin'
        assert response.content_type == 'application/json'

        # Update the plain file by adding some metadata.
        params = self.createParams.copy()
        params.update({
            'tags': [tag1Id, tag2Id],
            'description': u'plain updated',
            'dateElicited': u'01/01/2000',
            'speaker': speakerId,
            'utteranceType': u'Metalanguage Utterance'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=plainFileId), params, self.json_headers,
                                 extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert sorted([t['name'] for t in resp['tags']]) == [u'tag 1', u'tag 2']
        assert resp['description'] == u'plain updated'
        assert resp['speaker']['id'] == speakerId
        assert resp['filename'] == resp['name'] == u'multipart.wav'
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['enterer']['firstName'] == u'Admin'
        assert response.content_type == 'application/json'

        ########################################################################
        # Update a subinterval-referencing file
        ########################################################################

        # Create a subinterval-referencing audio file; reference one of the wav
        # files created earlier.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': plainFileId,
            'name': u'anyname',
            'start': 13.3,
            'end': 26.89,
            'tags': [tag1Id],
            'description': u'subinterval-referencing file',
            'dateElicited': u'01/01/2000',
            'speaker': speakerId,
            'utteranceType': u'Object Language Utterance'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_contrib)
        resp = json.loads(response.body)
        subintervalReferencingId = resp['id']
        assert resp['filename'] == None
        assert resp['name'] == u'anyname'
        assert resp['parentFile']['filename'] == u'multipart.wav'
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == None
        assert resp['parentFile']['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Contributor'
        assert resp['start'] == 13.3
        assert type(resp['start']) is float
        assert resp['end'] == 26.89
        assert type(resp['end']) is float
        assert resp['tags'][0]['id'] == tag1Id
        assert response.content_type == 'application/json'

        # Update the subinterval-referencing file.
        params = self.createParams.copy()
        params.update({
            'parentFile': plainFileId,
            'start': 13.3,
            'end': 26.89,
            'tags': [],
            'description': u'abc to def',
            'dateElicited': u'01/01/2010',
            'utteranceType': u'Metalanguage Utterance'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=subintervalReferencingId), params, self.json_headers,
                                 extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['parentFile']['id'] == plainFileId
        assert resp['name'] == resp['parentFile']['name']
        assert resp['tags'] == []
        assert resp['description'] == u'abc to def'
        assert resp['speaker'] == None
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert response.content_type == 'application/json'

        # Attempt a vacuous update and expect an error message.
        response = self.app.put(url('file', id=subintervalReferencingId), params, self.json_headers,
                                 extra_environ=self.extra_environ_contrib, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The update request failed because the submitted data were not new.'

        # Now restrict the parent file and verify that the child file does not
        # thereby become restricted.  This means that the metadata of a restricted
        # parent file may accessible to restricted users via the child file;
        # however, this is ok since the serve action still will not allow
        # the contents of the restricted file to be served to the restricted users.
        params = self.createParams.copy()
        params.update({
            'tags': [tag1Id, tag2Id, restrictedTagId],
            'description': u'plain updated',
            'dateElicited': u'01/01/2000',
            'speaker': speakerId,
            'utteranceType': u'Metalanguage Utterance'
        })
        params = json.dumps(params)
        response = self.app.put(url('file', id=plainFileId), params,
                    self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert u'restricted' in [t['name'] for t in resp['tags']]

        SRFile = Session.query(model.File).get(subintervalReferencingId)
        assert u'restricted' not in [t.name for t in SRFile.tags]

        ########################################################################
        # externally hosted file creation
        ########################################################################

        # Create a valid externally hosted file
        url_ = 'http://vimeo.com/54144270'
        params = self.createParamsEH.copy()
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'MIMEtype': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['description'] == u'A large video file I didn\'t want to upload here.'
        assert resp['url'] == url_

        # Update the externally hosted file
        params = self.createParamsEH.copy()
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'password': u'abc',
            'MIMEtype': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.',
            'dateElicited': u'12/29/1987'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['dateElicited'] == u'1987-12-29'
        assert resp['password'] == u'abc'

        # Attempt to update the externally hosted file with invalid params.
        params = self.createParamsEH.copy()
        params.update({
            'url': u'abc',      # Invalid
            'name': u'externally hosted file' * 200,    # too long
            'MIMEtype': u'zooboomafoo',                 # invalid
            'description': u'A large video file I didn\'t want to upload here.',
            'dateElicited': u'1987/12/29'               # wrong format
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['MIMEtype'] == u'The file upload failed because the file type zooboomafoo is not allowed.'
        assert resp['errors']['url'] == u'You must provide a full domain name (like abc.com)'
        assert resp['errors']['name'] == u'Enter a value not more than 255 characters long'
        assert resp['errors']['dateElicited'] == u'Please enter the date in the form mm/dd/yyyy'

    #@nottest
    def test_delete(self):
        """Tests that DELETE /files/id deletes the file with id=id and returns a JSON representation.

        If the id is invalid or unspecified, then JSON null or a 404 status code
        are returned, respectively.
        """
        # Add some objects to the db: a default application settings, a speaker
        # and a tag.
        applicationSettings = h.generateDefaultApplicationSettings()
        speaker = h.generateDefaultSpeaker()
        myContributor = h.generateDefaultUser()
        myContributor.username = u'uniqueusername'
        tag = model.Tag()
        tag.name = u'default tag'
        Session.add_all([applicationSettings, speaker, myContributor, tag])
        Session.commit()
        myContributor = Session.query(model.User).filter(
            model.User.username==u'uniqueusername').first()
        myContributorId = myContributor.id
        tagId = tag.id
        speakerId = speaker.id
        speakerFirstName = speaker.firstName

        # Count the original number of files
        fileCount = Session.query(model.File).count()

        # First, as myContributor, create a file to delete.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'filename': u'test_delete.jpg',
            'base64EncodedFile': b64encode(open(jpgFilePath).read()),
            'speaker': speakerId,
            'tags': [tagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        toDeleteId = resp['id']
        toDeleteName = resp['filename']
        assert resp['filename'] == u'test_delete.jpg'
        assert resp['tags'][0]['name'] == u'default tag'

        # Now count the files
        newFileCount = Session.query(model.File).count()
        assert newFileCount == fileCount + 1

        # Now, as the default contributor, attempt to delete the myContributor-
        # entered file we just created and expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.applicationSettings': True}
        response = self.app.delete(url('file', id=toDeleteId),
                                   extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        fileThatWasNotDeleted = Session.query(model.File).get(toDeleteId)
        filePath = os.path.join(self.filesPath, toDeleteName)
        assert os.path.exists(filePath)
        assert fileThatWasNotDeleted is not None
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # As myContributor, attempt to delete the file we just created and
        # expect to succeed.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.delete(url('file', id=toDeleteId),
                                   extra_environ=extra_environ)
        resp = json.loads(response.body)
        newFileCount = Session.query(model.File).count()
        tagOfDeletedFile = Session.query(model.Tag).get(
            resp['tags'][0]['id'])
        speakerOfDeletedFile = Session.query(model.Speaker).get(
            resp['speaker']['id'])
        assert isinstance(tagOfDeletedFile, model.Tag)
        assert isinstance(speakerOfDeletedFile, model.Speaker)
        assert newFileCount == fileCount

        # The deleted file will be returned to us, so the assertions from above
        # should still hold true.
        fileThatWasDeleted = Session.query(model.File).get(toDeleteId)
        filePath = os.path.join(self.filesPath, toDeleteName)
        assert not os.path.exists(filePath)
        assert 'old_test.jpg' not in os.listdir(self.filesPath)
        assert fileThatWasDeleted is None
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
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'filename': u'\u201Cte\u0301st delete\u201D.jpg',
            'base64EncodedFile': b64encode(open(jpgFilePath).read()),
            'speaker': speakerId,
            'tags': [tagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ)
        resp = json.loads(response.body)
        toDeleteId = resp['id']
        toDeleteName = resp['filename']
        assert resp['filename'] == u'\u201Cte\u0301st_delete\u201D.jpg'
        assert resp['tags'][0]['name'] == u'default tag'
        assert u'\u201Cte\u0301st_delete\u201D.jpg' in os.listdir(self.filesPath)
        response = self.app.delete(url('file', id=toDeleteId), extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert u'\u201Cte\u0301st_delete\u201D.jpg' not in os.listdir(self.filesPath)

        # Create a file, create a subinterval-referencing file that references
        # it and then delete the parent file.  Show that the child files become
        # "orphaned" but are not deleted.  Use case: user has uploaded an incorrect
        # parent file; must delete parent file, create a new one and then update
        # child files' parentFile attribute.

        # Create the parent WAV file.
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        params = self.createParams.copy()
        params.update({
            'filename': u'parent.wav',
            'base64EncodedFile': b64encode(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        parentId = resp['id']
        parentFilename = resp['filename']
        parentLossyFilename = resp['lossyFilename']

        # Create a subinterval-referencing audio file; reference one of the wav
        # files created earlier.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': parentId,
            'name': u'child',
            'start': 1,
            'end': 2,
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        childId = resp['id']
        assert resp['parentFile']['id'] == parentId

        # Show that the child file still exists after the parent has been deleted.
        assert parentFilename in os.listdir(self.filesPath)
        if self.create_reduced_size_file_copies and h.commandLineProgramInstalled(['ffmpeg']):
            assert parentLossyFilename in os.listdir(self.reducedFilesPath)
        response = self.app.delete(url('file', id=parentId), extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert parentFilename not in os.listdir(self.filesPath)
        assert parentLossyFilename not in os.listdir(self.reducedFilesPath)
        assert resp['filename'] == u'parent.wav'

        parent = Session.query(model.File).get(parentId)
        assert parent is None

        child = Session.query(model.File).get(childId)
        assert child is not None
        assert child.parentFile is None

        # Delete the child file
        response = self.app.delete(url('file', id=childId), extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'child'

    #@nottest
    def test_show(self):
        """Tests that GET /files/id returns a JSON file object, null or 404
        depending on whether the id is valid, invalid or unspecified,
        respectively.
        """

        # First create a test image file.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': b64encode(open(jpgFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        fileId = resp['id']
        assert resp['filename'] == u'old_test.jpg'
        assert resp['MIMEtype'] == u'image/jpeg'
        assert resp['size'] == jpgFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 1

        # Then create a form associated to the image file just created and make sure
        # we can access the form via the file.forms backreference.
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'test',
            'translations': [{'transcription': u'test', 'grammaticality': u''}],
            'files': [fileId]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        assert type(resp) == type({})
        assert resp['transcription'] == u'test'
        assert resp['translations'][0]['transcription'] == u'test'
        assert resp['morphemeBreakIDs'] == None
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['files'][0]['filename'] == u'old_test.jpg'

        # GET the image file and make sure we see the associated form.
        response = self.app.get(url('file', id=fileId), headers=self.json_headers,
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
        users = h.getUsers()
        contributorId = [u for u in users if u.role == u'contributor'][0].id

        # Then add another contributor and a restricted tag.
        restrictedTag = h.generateRestrictedTag()
        myContributor = h.generateDefaultUser()
        myContributorFirstName = u'Mycontributor'
        myContributor.firstName = myContributorFirstName
        myContributor.username = u'uniqueusername'
        Session.add_all([restrictedTag, myContributor])
        Session.commit()
        myContributor = Session.query(model.User).filter(
            model.User.firstName == myContributorFirstName).first()
        myContributorId = myContributor.id

        # Then add the default application settings with myContributor as the
        # only unrestricted user.
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.unrestrictedUsers = [myContributor]
        Session.add(applicationSettings)
        Session.commit()

        # Finally, issue a POST request to create the restricted file with
        # the *default* contributor as the enterer.
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64EncodedFile': b64encode(open(wavFilePath).read()),
            'tags': [h.getTags()[0].id]    # the restricted tag should be the only one
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restrictedFileId = resp['id']
        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted myContributor should all be able to view the file.
        # The viewer should get a 403 error when attempting to view this file.
        # An administrator should be able to view this file.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('file', id=restrictedFileId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # The default contributor (qua enterer) should be able to view this file.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('file', id=restrictedFileId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # Mycontributor (an unrestricted user) should be able to view this
        # restricted file.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('file', id=restrictedFileId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # A (not unrestricted) viewer should *not* be able to view this file.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('file', id=restrictedFileId),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        # Remove Mycontributor from the unrestricted users list and access will be denied.
        applicationSettings = h.getApplicationSettings()
        applicationSettings.unrestrictedUsers = []
        Session.add(applicationSettings)
        Session.commit()
        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view this restricted file.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('file', id=restrictedFileId),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        # Remove the restricted tag from the file and the viewer should now be
        # able to view it too.
        restrictedFile = Session.query(model.File).get(restrictedFileId)
        restrictedFile.tags = []
        Session.add(restrictedFile)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('file', id=restrictedFileId),
                        headers=self.json_headers, extra_environ=extra_environ)
        assert response.content_type == 'application/json'

    #@nottest
    def test_edit(self):
        """Tests that GET /files/id/edit returns a JSON object of data necessary to edit the file with id=id.

        The JSON object is of the form {'file': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Add the default application settings and the restricted tag.
        applicationSettings = h.generateDefaultApplicationSettings()
        restrictedTag = h.generateRestrictedTag()
        Session.add_all([restrictedTag, applicationSettings])
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        contributor = [u for u in h.getUsers() if u.role == u'contributor'][0]
        contributorId = contributor.id

        # Create a restricted file.
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.wav',
            'base64EncodedFile': b64encode(open(wavFilePath).read()),
            'tags': [restrictedTag.id]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        self.extra_environ_admin)
        resp = json.loads(response.body)
        restrictedFileId = resp['id']

        # As a (not unrestricted) contributor, attempt to call edit on the
        # restricted form and expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.applicationSettings': True}
        response = self.app.get(url('edit_file', id=restrictedFileId),
                                extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_file', id=restrictedFileId), status=401)
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
        response = self.app.get(url('edit_file', id=restrictedFileId),
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
        #    string that matches the most recent datetimeModified value of the
        #    store in question.

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        speaker = h.generateDefaultSpeaker()
        tag = model.Tag()
        tag.name = u'name'
        Session.add_all([applicationSettings, speaker, tag])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'tags': h.getMiniDictsGetter('Tag')(),
            'speakers': h.getMiniDictsGetter('Speaker')(),
            'users': h.getMiniDictsGetter('User')(),
            'utteranceTypes': h.utteranceTypes,
            'allowedFileTypes': h.allowedFileTypes
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
            # recent Tag.datetimeModified value: 'tags' *will* be in response.
            'tags': datetime.datetime.utcnow().isoformat(),
        }
        response = self.app.get(url('edit_file', id=restrictedFileId), params,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['data']['tags'] == data['tags']
        assert resp['data']['speakers'] == []
        assert resp['data']['users'] == data['users']
        assert resp['data']['utteranceTypes'] == data['utteranceTypes']
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

    #@nottest
    def test_serve(self):
        """Tests that GET /files/serve/id returns the file with name id from
        the permanent store, i.e., from onlinelinguisticdatabase/files/.
        """

        extra_environ_admin = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        extra_environ_contrib = {'test.authentication.role': 'contributor',
                         'test.applicationSettings': True}

        # Create a restricted wav file.
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTagId = restrictedTag.id
        here = self.here
        testFilesPath = os.path.join(here, 'test_files')
        wavFilename = u'old_test.wav'
        wavFilePath = os.path.join(testFilesPath, wavFilename)
        wavFileSize = os.path.getsize(wavFilePath)
        wavFileBase64 = b64encode(open(wavFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': wavFilename,
            'base64EncodedFile': wavFileBase64,
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ_admin)
        resp = json.loads(response.body)
        wavFilename = resp['filename']
        wavFileId = resp['id']

        # Retrieve the file data as the admin who entered it
        response = self.app.get(url(controller='files', action='serve', id=wavFileId),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        responseBase64 = b64encode(response.body)
        assert wavFileBase64 == responseBase64
        assert guess_type(wavFilename)[0] == response.headers['Content-Type']
        assert wavFileSize == int(response.headers['Content-Length'])

        # Attempt to retrieve the file without authentication and expect to fail (401).
        response = self.app.get(url(controller='files', action='serve', id=wavFileId),
            headers=self.json_headers, status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Attempt to retrieve the restricted file data as the contrib and expect to fail.
        response = self.app.get(url(controller='files', action='serve', id=wavFileId),
            headers=self.json_headers, extra_environ=extra_environ_contrib, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        assert response.content_type == 'application/json'

        # Attempt to serve an externally hosted file and expect a 400 status response.

        # Create a valid externally hosted file
        params = self.createParamsEH.copy()
        url_ = 'http://vimeo.com/54144270'
        params.update({
            'url': url_,
            'name': u'externally hosted file',
            'MIMEtype': u'video/mpeg',
            'description': u'A large video file I didn\'t want to upload here.'
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        ehFileId = resp['id']

        # Attempt to retrieve the externally hosted file's "data" and expect a 400 response.
        response = self.app.get(url(controller='files', action='serve', id=ehFileId),
            headers=self.json_headers, extra_environ=extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'The content of file %s is stored elsewhere at %s' % (ehFileId, url_)
        assert response.content_type == 'application/json'

        # Request the content of a subinterval-referencing file and expect to receive
        # the file data from its parentFile

        # Create a subinterval-referencing audio file; reference the wav created above.
        params = self.createParamsSR.copy()
        params.update({
            'parentFile': wavFileId,
            'name': u'subinterval_x',
            'start': 1.3,
            'end': 2.6
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        srFileId = resp['id']

        # Retrieve the parent file's file data when requesting that of the child.
        response = self.app.get(url(controller='files', action='serve', id=srFileId),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        responseBase64 = b64encode(response.body)
        assert wavFileBase64 == responseBase64
        assert guess_type(wavFilename)[0] == response.headers['Content-Type']

        # Retrieve the reduced file data of the wav file created above.
        if self.create_reduced_size_file_copies and h.commandLineProgramInstalled(['ffmpeg']):
            response = self.app.get(url(controller='files', action='serve_reduced', id=wavFileId),
                headers=self.json_headers, extra_environ=extra_environ_admin)
            responseBase64 = b64encode(response.body)
            assert len(wavFileBase64) > len(responseBase64)
            assert response.content_type == h.guess_type('x.%s' % self.preferred_lossy_audio_format)[0]
        else:
            response = self.app.get(url(controller='files', action='serve_reduced', id=wavFileId),
                headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
            resp = json.loads(response.body)
            assert resp['error'] == u'There is no size-reduced copy of file %s' % wavFileId
            assert response.content_type == 'application/json'

        # Retrieve the reduced file of the wav-subinterval-referencing file above
        if self.create_reduced_size_file_copies and h.commandLineProgramInstalled(['ffmpeg']):
            response = self.app.get(url(controller='files', action='serve_reduced', id=srFileId),
                headers=self.json_headers, extra_environ=extra_environ_admin)
            srResponseBase64 = b64encode(response.body)
            assert len(wavFileBase64) > len(srResponseBase64)
            assert srResponseBase64 == responseBase64
            assert response.content_type == h.guess_type('x.%s' % self.preferred_lossy_audio_format)[0]
        else:
            response = self.app.get(url(controller='files', action='serve_reduced', id=srFileId),
                headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
            resp = json.loads(response.body)
            assert resp['error'] == u'There is no size-reduced copy of file %s' % srFileId
            assert response.content_type == 'application/json'

        # Create an image file and retrieve its contents and resized contents
        jpgFilename = u'large_image.jpg'
        jpgFilePath = os.path.join(testFilesPath, jpgFilename)
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = b64encode(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': jpgFilename,
            'base64EncodedFile': jpgFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ_admin)
        resp = json.loads(response.body)
        jpgFilename = resp['filename']
        jpgFileId = resp['id']

        # Get the image file's contents
        response = self.app.get(url(controller='files', action='serve', id=jpgFileId),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        responseBase64 = b64encode(response.body)
        assert jpgFileBase64 == responseBase64
        assert guess_type(jpgFilename)[0] == response.headers['Content-Type']
        assert jpgFileSize == int(response.headers['Content-Length'])

        # Get the reduced image file's contents
        if self.create_reduced_size_file_copies and Image:
            response = self.app.get(url(controller='files', action='serve_reduced', id=jpgFileId),
                headers=self.json_headers, extra_environ=extra_environ_admin)
            responseBase64 = b64encode(response.body)
            assert jpgFileBase64 > responseBase64
            assert guess_type(jpgFilename)[0] == response.headers['Content-Type']
        else:
            response = self.app.get(url(controller='files', action='serve_reduced', id=jpgFileId),
                headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
            resp = json.loads(response.body)
            assert resp['error'] == u'There is no size-reduced copy of file %s' % jpgFileId

        # Attempt to get the reduced contents of a file that has none (i.e., no
        # lossyFilename value) and expect to fail.

        # Create a .ogg file and retrieve its contents and fail to retrieve its resized contents
        oggFilename = u'old_test.ogg'
        oggFilePath = os.path.join(testFilesPath, oggFilename)
        oggFileSize = os.path.getsize(oggFilePath)
        oggFileBase64 = b64encode(open(oggFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': oggFilename,
            'base64EncodedFile': oggFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, extra_environ_admin)
        resp = json.loads(response.body)
        oggFilename = resp['filename']
        oggFileId = resp['id']

        # Get the .ogg file's contents
        response = self.app.get(url(controller='files', action='serve', id=oggFileId),
            headers=self.json_headers, extra_environ=extra_environ_admin)
        responseBase64 = b64encode(response.body)
        assert oggFileBase64 == responseBase64
        assert guess_type(oggFilename)[0] == response.headers['Content-Type']
        assert oggFileSize == int(response.headers['Content-Length'])

        # Attempt to get the reduced image file's contents and expect to fail
        response = self.app.get(url(controller='files', action='serve_reduced', id=oggFileId),
            headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no size-reduced copy of file %s' % oggFileId

        # Invalid id
        response = self.app.get(url(controller='files', action='serve', id=123456789012),
            headers=self.json_headers, extra_environ=extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no file with id 123456789012'

    #@nottest
    def test_file_reduction(self):
        """Verifies that reduced-size copies of image and wav files are created in files/reduced_files
        and that the names of these reduced-size files is returned as the lossyFilename
        attribute.

        Note that this test will fail if create_reduced_size_file_copies is set
        to 0 in the config file.
        """
        def getSize(path):
            return os.stat(path).st_size

        # Create a JPG file that will not be reduced because it is already small enough
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = b64encode(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': u'old_test.jpg',
            'base64EncodedFile': jpgFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert resp['filename'] == u'old_test.jpg'
        assert resp['MIMEtype'] == u'image/jpeg'
        assert resp['size'] == jpgFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['lossyFilename'] == None
        assert fileCount == 1
        assert len(os.listdir(self.reducedFilesPath)) == 0

        # Create a large JPEG file and expect a reduced-size .jpg to be created in
        # files/reduced_files.
        filename = u'large_image.jpg'
        jpgFilePath = os.path.join(self.testFilesPath, filename)
        jpgReducedFilePath = os.path.join(self.reducedFilesPath, filename)
        jpgFileBase64 = b64encode(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': filename,
            'base64EncodedFile': jpgFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        newFileCount = Session.query(model.File).count()
        assert newFileCount == fileCount + 1
        assert resp['filename'] == filename
        assert resp['MIMEtype'] == u'image/jpeg'
        assert resp['enterer']['firstName'] == u'Admin'
        if self.create_reduced_size_file_copies and Image:
            assert resp['lossyFilename'] == filename
            assert resp['lossyFilename'] in os.listdir(self.reducedFilesPath)
            assert getSize(jpgFilePath) > getSize(jpgReducedFilePath)
        else:
            assert resp['lossyFilename'] is None
            assert not os.path.isfile(jpgReducedFilePath)

        # Create a large GIF file and expect a reduced-size .gif to be created in
        # files/reduced_files.
        filename = u'large_image.gif'
        gifFilePath = os.path.join(self.testFilesPath, filename)
        gifReducedFilePath = os.path.join(self.reducedFilesPath, filename)
        gifFileBase64 = b64encode(open(gifFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': filename,
            'base64EncodedFile': gifFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = newFileCount
        newFileCount = Session.query(model.File).count()
        assert newFileCount == fileCount + 1
        assert resp['filename'] == filename
        assert resp['MIMEtype'] == u'image/gif'
        assert resp['enterer']['firstName'] == u'Admin'
        if self.create_reduced_size_file_copies and Image:
            assert resp['lossyFilename'] == filename
            assert resp['lossyFilename'] in os.listdir(self.reducedFilesPath)
            assert getSize(gifFilePath) > getSize(gifReducedFilePath)
        else:
            assert resp['lossyFilename'] is None
            assert not os.path.isfile(gifReducedFilePath)

        # Create a large PNG file and expect a reduced-size .png to be created in
        # files/reduced_files.
        filename = 'large_image.png'
        pngFilePath = os.path.join(self.testFilesPath, filename)
        pngReducedFilePath = os.path.join(self.reducedFilesPath, filename)
        params = self.createParamsBasic.copy()
        params.update({'filename': filename})
        response = self.app.post(url('/files'), params,
                                 extra_environ=self.extra_environ_admin,
                                 upload_files=[('filedata', pngFilePath)])
        resp = json.loads(response.body)
        fileCount = newFileCount
        newFileCount = Session.query(model.File).count()
        assert newFileCount == fileCount + 1
        assert resp['filename'] == filename
        assert resp['MIMEtype'] == u'image/png'
        assert resp['enterer']['firstName'] == u'Admin'
        if self.create_reduced_size_file_copies and Image:
            assert resp['lossyFilename'] == filename
            assert resp['lossyFilename'] in os.listdir(self.reducedFilesPath)
            assert getSize(pngFilePath) > getSize(pngReducedFilePath)
        else:
            assert resp['lossyFilename'] is None
            assert not os.path.isfile(pngReducedFilePath)

        # Test copying .wav files to .ogg/.mp3

        format_ = self.preferred_lossy_audio_format

        # Create a WAV file for which an .ogg/.mp3 Vorbis copy will be created in
        # files/reduced_files.
        filename = 'old_test.wav'
        lossyFilename = u'%s.%s' % (os.path.splitext(filename)[0], format_)
        lossyFilePath = os.path.join(self.reducedFilesPath, lossyFilename)
        wavFilePath = os.path.join(self.testFilesPath, filename)
        wavFileSize = os.path.getsize(wavFilePath)
        wavFileBase64 = b64encode(open(wavFilePath).read())
        params = self.createParams.copy()
        params.update({
            'filename': filename,
            'base64EncodedFile': wavFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = newFileCount
        newFileCount = Session.query(model.File).count()
        assert resp['filename'] == filename
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert newFileCount == fileCount + 1
        if self.create_reduced_size_file_copies and h.commandLineProgramInstalled(['ffmpeg']):
            assert resp['lossyFilename'] == lossyFilename
            assert resp['lossyFilename'] in os.listdir(self.reducedFilesPath)
            assert getSize(wavFilePath) > getSize(lossyFilePath)
        else:
            assert resp['lossyFilename'] is None
            assert not os.path.isfile(lossyFilePath)

    #@nottest
    def test_new_search(self):
        """Tests that GET /files/new_search returns the search parameters for searching the files resource."""
        queryBuilder = SQLAQueryBuilder('File')
        response = self.app.get(url('/files/new_search'), headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['searchParameters'] == h.getSearchParameters(queryBuilder)
