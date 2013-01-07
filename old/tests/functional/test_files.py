import datetime
import logging
import simplejson as json
import os
from base64 import encodestring
from nose.tools import nottest
from paste.deploy import appconfig
from mimetypes import guess_type
from old.tests import *
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h

log = logging.getLogger(__name__)


class TestFilesController(TestController):

    here = appconfig('config:development.ini', relative_to='.')['here']
    filesPath = os.path.join(here, 'files')
    testFilesPath = os.path.join(here, 'test_files')

    createParams = {
        'name': u'',
        'description': u'',
        'dateElicited': u'',    # mm/dd/yyyy
        'elicitor': u'',
        'speaker': u'',
        'utteranceType': u'',
        'embeddedFileMarkup': u'',
        'embeddedFilePassword': u'',
        'tags': [],
        'forms': [],
        'file': ''      # file data Base64 encoded
    }

    createFormParams = {
            'transcription': u'',
            'phoneticTranscription': u'',
            'narrowPhoneticTranscription': u'',
            'morphemeBreak': u'',
            'grammaticality': u'',
            'morphemeGloss': u'',
            'glosses': [{'gloss': u'', 'glossGrammaticality': u''}],
            'comments': u'',
            'speakerComments': u'',
            'elicitationMethod': u'',
            'tags': [],
            'syntacticCategory': u'',
            'speaker': u'',
            'elicitor': u'',
            'verifier': u'',
            'source': u'',
            'dateElicited': u'',     # mm/dd/yyyy
            'files': []
        }

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
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
        wavFileBase64Encoded = encodestring(open(wavFilePath).read())

        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64Encoded = encodestring(open(jpgFilePath).read())

        # Create the restricted file.
        params = self.createParams.copy()
        params.update({
            'name': u'test_restricted_file.wav',
            'file': wavFileBase64Encoded,
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
            'name': u'test_unrestricted_file.jpg',
            'file': jpgFileBase64Encoded
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
        assert resp[0]['name'] == u'test_restricted_file.wav'
        assert resp[1]['name'] == u'test_unrestricted_file.jpg'

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
            file.name = u'name_%d.jpg' % index
            return file
        files = [createFileFromIndex(i) for i in range(1, 101)]
        Session.add_all(files)
        Session.commit()
        files = h.getFiles()
        restrictedTag = h.getRestrictedTag()
        for file in files:
            if int(file.name.split('_')[1].split('.')[0]) % 2 == 0:
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
        assert resp[0]['name'] == u'name_1.jpg'
        assert resp[0]['id'] == files[0].id

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('files'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['name'] == files[46].name

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'File', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('files'), orderByParams,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        resultSet = sorted([f.name for f in files], reverse=True)
        assert resultSet == [f['name'] for f in resp]

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'File', 'orderByAttribute': 'name',
                     'orderByDirection': 'desc', 'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('files'), params,
                        headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resultSet[46] == resp['items'][0]['name']

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
        assert resp['items'][0]['name'] == u'name_%d.jpg' % (
            ((itemsPerPage * (page - 1)) * 2) + 1)

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'File', 'orderByAttribute': 'name',
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

    #@nottest
    def test_create(self):
        """Tests that POST /files correctly creates a new file."""

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
            'name': u'old_test.wav',
            'file': encodestring(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert resp['name'] == u'old_test.wav'
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 1

        # Create a test image file.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = encodestring(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'name': u'old_test.jpg',
            'file': jpgFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        fileId = resp['id']
        assert resp['name'] == u'old_test.jpg'
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
        Session.add_all([tag1, tag2])
        Session.commit()
        tag1Id = tag1.id
        tag2Id = tag2.id

        # Then create a form to associate.
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'test',
            'glosses': [{'gloss': u'test', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formId = resp['id']

        # Now create the file with forms and tags
        params = self.createParams.copy()
        params.update({
            'name': u'old_test.jpg',
            'file': jpgFileBase64,
            'tags': [tag1Id, tag2Id],
            'forms': [formId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        fileId = resp['id']
        assert resp['name'][:9] == u'old_test_'
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
            'name': u'',                    # empty; not allowed
            'file': '',                     # empty; not allowed
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
        assert resp['errors']['name'] == u'Please enter a value'
        assert resp['errors']['file']== u'Please enter a value'
        assert fileCount == 3

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
            'name': u'old_test.wav',
            'file': encodestring(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        assert resp['name'] == u'old_test.wav'
        assert resp['MIMEtype'] == u'audio/x-wav'
        assert resp['size'] == wavFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 1

        # First create the restricted tag.
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTagId = restrictedTag.id

        # Then create two forms, one restricted and one not.
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'restricted',
            'glosses': [{'gloss': u'restricted', 'glossGrammaticality': u''}],
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
            'glosses': [{'gloss': u'unrestricted', 'glossGrammaticality': u''}]
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
        jpgFileBase64 = encodestring(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'name': u'old_test.jpg',
            'file': jpgFileBase64,
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
        jpgFileBase64 = encodestring(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'name': u'old_test.jpg',
            'file': jpgFileBase64,
            'forms': [unrestrictedFormId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 contrib)
        resp = json.loads(response.body)
        unrestrictedFileId = resp['id']
        assert resp['name'] == u'old_test.jpg'
        assert resp['forms'][0]['transcription'] == u'unrestricted'

        # Now, as a(n unrestricted) administrator, attempt to create a file and
        # associate it to a restricted form -- expect (a) to succeed and (b) to
        # find that the file is now restricted.
        jpgFilePath = os.path.join(self.testFilesPath, 'old_test.jpg')
        jpgFileSize = os.path.getsize(jpgFilePath)
        jpgFileBase64 = encodestring(open(jpgFilePath).read())
        params = self.createParams.copy()
        params.update({
            'name': u'old_test.jpg',
            'file': jpgFileBase64,
            'forms': [restrictedFormId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        indirectlyRestrictedFileId = resp['id']
        assert resp['name'][:8] == u'old_test'
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
            'name': u'old_test.jpg',
            'file': jpgFileBase64
        })
        params = json.dumps(unrestrictedFileParams)
        response = self.app.post(url('files'), params, self.json_headers, admin)
        resp = json.loads(response.body)
        unrestrictedFileId = resp['id']
        assert resp['name'][:8] == u'old_test'

        # As a restricted contributor, attempt to update the unrestricted file
        # just created by associating it to a restricted form -- expect to fail.
        unrestrictedFileParams.update({'forms': [restrictedFormId]})
        params = json.dumps(unrestrictedFileParams)
        response = self.app.put(url('file', id=unrestrictedFileId), params,
                                self.json_headers, contrib, status=400)
        resp = json.loads(response.body)
        assert u'You are not authorized to access the form with id %d.' % restrictedFormId in \
            resp['errors']['forms']

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


    #@nottest
    def test_create_large(self):
        """Tests that POST /files correctly creates a large file.

        WARNING 1: long-running test.

        WARNING: 2: if a large file named old_test_long.wav does not exist in
        test_files, this test will pass vacuously.  I don't want to include such
        a large file in the code base so this file needs to be created if one
        wants this test to run.
        """
        wavFileName = u'old_test_long.wav'
        wavFilePath = os.path.join(self.testFilesPath, wavFileName)
        if os.path.exists(wavFilePath):
            # Create a large (>60 MB) test audio file.
            wavFileSize = os.path.getsize(wavFilePath)
            params = self.createParams.copy()
            params.update({
                'name': wavFileName,
                'file': encodestring(open(wavFilePath).read())
            })
            params = json.dumps(params)
            response = self.app.post(url('files'), params, self.json_headers,
                                     self.extra_environ_admin)
            resp = json.loads(response.body)
            fileCount = Session.query(model.File).count()
            assert resp['name'] == wavFileName
            assert resp['MIMEtype'] == u'audio/x-wav'
            assert resp['size'] == wavFileSize
            assert resp['enterer']['firstName'] == u'Admin'
            assert fileCount == 1

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

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        restrictedTag = h.generateRestrictedTag()
        speaker = h.generateDefaultSpeaker()
        Session.add_all([applicationSettings, restrictedTag, speaker])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'tags': h.getTags(),
            'speakers': h.getSpeakers(),
            'users': h.getUsers(),
            'utteranceTypes': h.utteranceTypes
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

        # Create a file to update.
        wavFilePath = os.path.join(self.testFilesPath, 'old_test.wav')
        wavFileSize = os.path.getsize(wavFilePath)
        params = self.createParams.copy()
        originalName = u'test_update_name.jpg'
        params.update({
            'name': originalName,
            'tags': [restrictedTag.id],
            'description': u'description',
            'file': encodestring(open(wavFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        id = int(resp['id'])
        newFileCount = Session.query(model.File).count()
        assert resp['name'] == originalName
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
        assert newFileCount == fileCount + 1

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
            'name': u'test_delete.jpg',
            'file': encodestring(open(jpgFilePath).read()),
            'speaker': speakerId,
            'tags': [tagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        toDeleteId = resp['id']
        toDeleteName = resp['name']
        assert resp['name'] == u'test_delete.jpg'
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
        assert resp['name'] == u'test_delete.jpg'

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('file', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no file with id %s' % id in json.loads(response.body)[
            'error']

        # Delete without an id
        response = self.app.delete(url('file', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

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
            'name': u'old_test.jpg',
            'file': encodestring(open(jpgFilePath).read())
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        fileCount = Session.query(model.File).count()
        fileId = resp['id']
        assert resp['name'] == u'old_test.jpg'
        assert resp['MIMEtype'] == u'image/jpeg'
        assert resp['size'] == jpgFileSize
        assert resp['enterer']['firstName'] == u'Admin'
        assert fileCount == 1

        # Then create a form associated to the image file just created and make sure
        # we can access the form via the file.forms backreference.
        params = self.createFormParams.copy()
        params.update({
            'transcription': u'test',
            'glosses': [{'gloss': u'test', 'glossGrammaticality': u''}],
            'files': [fileId]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        assert type(resp) == type({})
        assert resp['transcription'] == u'test'
        assert resp['glosses'][0]['gloss'] == u'test'
        assert resp['morphemeBreakIDs'] == [[[]]]
        assert resp['enterer']['firstName'] == u'Admin'
        assert resp['files'][0]['name'] == u'old_test.jpg'

        # GET the image file and make sure we see the associated form.
        response = self.app.get(url('file', id=fileId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['forms'][0]['transcription'] == u'test'
        assert resp['name'] == u'old_test.jpg'

        # Invalid id
        id = 100000000000
        response = self.app.get(url('file', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no file with id %s' % id in json.loads(response.body)[
            'error']

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
            'name': u'old_test.wav',
            'file': encodestring(open(wavFilePath).read()),
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
            'name': u'old_test.wav',
            'file': encodestring(open(wavFilePath).read()),
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

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_file', id=restrictedFileId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_file', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no file with id %s' % id in json.loads(response.body)[
            'error']

        # No id
        response = self.app.get(url('edit_file', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_file', id=restrictedFileId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['file']['name'] == u'old_test.wav'

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
            'tags': h.getTags(),
            'speakers': h.getSpeakers(),
            'users': h.getUsers(),
            'utteranceTypes': h.utteranceTypes
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

        # Invalid id with GET params.  It should still return 'null'.
        params = {
            # If id were valid, this would cause a speakers array to be returned
            # also.
            'speakers': 'True',
        }
        response = self.app.get(url('edit_file', id=id), params,
                            extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no file with id %s' % id in json.loads(response.body)[
            'error']

    #@nottest
    def test_retrieve(self):
        """Tests that GET /files/retrieve/id returns the file with name id from
        the permanent store, i.e., from old/files/.
        """

        # Create a file.
        here = appconfig('config:development.ini', relative_to='.')['here']
        testFilesPath = os.path.join(here, 'test_files')
        wavFileName = u'old_test.wav'
        wavFilePath = os.path.join(testFilesPath, wavFileName)
        wavFileSize = os.path.getsize(wavFilePath)
        wavFileBase64 = encodestring(open(wavFilePath).read())
        params = self.createParams.copy()
        params.update({
            'name': wavFileName,
            'file': wavFileBase64
        })
        params = json.dumps(params)
        response = self.app.post(url('files'), params, self.json_headers,
                        self.extra_environ_admin)
        resp = json.loads(response.body)

        # Retrieve the file data
        response = self.app.get(url(controller='files', action='retrieve', id=wavFileName),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        responseBase64 = encodestring(response.body)
        assert wavFileBase64 == responseBase64
        assert guess_type(wavFileName)[0] == response.headers['Content-Type']
        assert wavFileSize == int(response.headers['Content-Length'])

        # Attempt to retrieve the file without authentication and expect to fail (401).
        response = self.app.get(url(controller='files', action='retrieve', id=wavFileName),
            headers=self.json_headers, status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
