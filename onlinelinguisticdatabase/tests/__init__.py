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

"""Pylons application test package

This package assumes the Pylons environment is already loaded, such as
when this script is imported from the `nosetests --with-pylons=test.ini`
command.

This module initializes the application via ``websetup`` (`paster
setup-app`) and provides the base testing objects.
"""
import StringIO
import gzip
import os
import webtest
from paste.deploy import appconfig
from unittest import TestCase
from paste.script.appinstall import SetupCommand
from pylons import url
from routes.util import URLGenerator
import pylons.test
import onlinelinguisticdatabase.lib.helpers as h
from paste.deploy.converters import asbool
from onlinelinguisticdatabase.model.meta import Session

__all__ = ['environ', 'url', 'TestController']

# Invoke websetup with the current config file
SetupCommand('setup-app').run([pylons.test.pylonsapp.config['__file__']])

environ = {}

class TestController(TestCase):

    def __init__(self, *args, **kwargs):
        wsgiapp = pylons.test.pylonsapp
        config = wsgiapp.config
        self.app = webtest.TestApp(wsgiapp)
        url._push_object(URLGenerator(config['routes.map'], environ))
        self.__setattrs__()
        self.__setcreateparams__()
        TestCase.__init__(self, *args, **kwargs)

    def __setattrs__(self):
        self.extra_environ_view = {'test.authentication.role': u'viewer'}
        self.extra_environ_contrib = {'test.authentication.role': u'contributor'}
        self.extra_environ_admin = {'test.authentication.role': u'administrator'}
        self.extra_environ_view_appset = {'test.authentication.role': u'viewer',
                                            'test.applicationSettings': True}
        self.extra_environ_contrib_appset = {'test.authentication.role': u'contributor',
                                            'test.applicationSettings': True}
        self.extra_environ_admin_appset = {'test.authentication.role': u'administrator',
                                            'test.applicationSettings': True}

        self.json_headers = {'Content-Type': 'application/json'}

        config = self.config = appconfig('config:test.ini', relative_to='.')
        self.here = config['here']
        self.filesPath = h.getOLDDirectoryPath('files', config=config)
        self.reducedFilesPath = h.getOLDDirectoryPath('reduced_files', config=config)
        self.testFilesPath = os.path.join(self.here, 'onlinelinguisticdatabase', 'tests',
                             'data', 'files')
        self.create_reduced_size_file_copies = asbool(config.get(
            'create_reduced_size_file_copies', False))
        self.preferred_lossy_audio_format = config.get('preferred_lossy_audio_format', 'ogg')
        self.corporaPath = h.getOLDDirectoryPath('corpora', config=config)
        self.testDatasetsPath = os.path.join(self.here, 'onlinelinguisticdatabase',
                            'tests', 'data', 'datasets')
        self.testScriptsPath = os.path.join(self.here, 'onlinelinguisticdatabase',
                            'tests', 'scripts')
        self.loremipsum100Path = os.path.join(self.testDatasetsPath, 'loremipsum_100.txt')
        self.loremipsum1000Path = os.path.join(self.testDatasetsPath , 'loremipsum_1000.txt')
        self.loremipsum10000Path = os.path.join(self.testDatasetsPath, 'loremipsum_10000.txt')
        self.usersPath = h.getOLDDirectoryPath('users', config=config)
        self.morphologiesPath = h.getOLDDirectoryPath('morphologies', config=config)
        self.phonologiesPath = h.getOLDDirectoryPath('phonologies', config=config)
        self.testPhonologiesPath = os.path.join(self.here, 'onlinelinguisticdatabase',
                            'tests', 'data', 'phonologies')
        self.testPhonologyScriptPath = os.path.join(
                self.testPhonologiesPath, 'test_phonology.script')
        self.testMalformedPhonologyScriptPath = os.path.join(
                self.testPhonologiesPath, 'test_phonology_malformed.script')
        self.testPhonologyNoPhonologyScriptPath = os.path.join(
                self.testPhonologiesPath, 'test_phonology_malformed.script')
        self.testMediumPhonologyScriptPath = os.path.join(
                self.testPhonologiesPath, 'test_phonology_medium.script')
        self.testLargePhonologyScriptPath = os.path.join(
                self.testPhonologiesPath, 'test_phonology_large.script')
        self.testPhonologyTestlessScriptPath = os.path.join(
                self.testPhonologiesPath, 'test_phonology_no_tests.script')

    def __setcreateparams__(self):

        self.applicationSettingsCreateParams = {
            'objectLanguageName': u'',
            'objectLanguageId': u'',
            'metalanguageName': u'',
            'metalanguageId': u'',
            'metalanguageInventory': u'',
            'orthographicValidation': u'None', # Value should be one of [u'None', u'Warning', u'Error']
            'narrowPhoneticInventory': u'',
            'narrowPhoneticValidation': u'None',
            'broadPhoneticInventory': u'',
            'broadPhoneticValidation': u'None',
            'morphemeBreakIsOrthographic': u'',
            'morphemeBreakValidation': u'None',
            'phonemicInventory': u'',
            'morphemeDelimiters': u'',
            'punctuation': u'',
            'grammaticalities': u'',
            'unrestrictedUsers': [],        # A list of user ids
            'storageOrthography': u'',        # An orthography id
            'inputOrthography': u'',          # An orthography id
            'outputOrthography': u''         # An orthography id
        }
        self.collectionCreateParams = {
            'title': u'',
            'type': u'',
            'url': u'',
            'description': u'',
            'markupLanguage': u'',
            'contents': u'',
            'speaker': u'',
            'source': u'',
            'elicitor': u'',
            'enterer': u'',
            'dateElicited': u'',
            'tags': [],
            'files': []
        }
        self.corpusCreateParams = {
            'name': u'',
            'description': u'',
            'content': u'',
            'formSearch': u'',
            'tags': []
        }
        self.fileCreateParams = {
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
        self.fileCreateParamsBase64 = {
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
        self.fileCreateParamsMPFD = {
            'filename': u'',        # Will be filtered out on update requests
            'description': u'',
            'dateElicited': u'',    # mm/dd/yyyy
            'elicitor': u'',
            'speaker': u'',
            'utteranceType': u'',
            'tags-0': u'',
            'forms-0': u''
        }
        self.fileCreateParamsSubRef = {
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
        self.fileCreateParamsExtHost = {
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
        self.formCreateParams = {
            'transcription': u'',
            'phoneticTranscription': u'',
            'narrowPhoneticTranscription': u'',
            'morphemeBreak': u'',
            'grammaticality': u'',
            'morphemeGloss': u'',
            'translations': [],
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
            'syntax': u'',
            'semantics': u''
        }
        self.formSearchCreateParams = {
            'name': u'',
            'search': u'',
            'description': u'',
            'searcher': u''
        }
        self.morphologyCreateParams = {
            'name': u'',
            'description': u'',
            'lexiconCorpus': u'',
            'rulesCorpus': u''
        }
        self.orthographyCreateParams = {
            'name': u'',
            'orthography': u'',
            'lowercase': False,
            'initialGlottalStops': True
        }
        self.pageCreateParams = {
            'name': u'',
            'heading': u'',
            'markupLanguage': u'',
            'content': u'',
            'html': u''
        }
        self.phonologyCreateParams = {
            'name': u'',
            'description': u'',
            'script': u''
        }
        self.sourceCreateParams = {
            'file': u'',
            'type': u'',
            'key': u'',
            'address': u'',
            'annote': u'',
            'author': u'',
            'booktitle': u'',
            'chapter': u'',
            'crossref': u'',
            'edition': u'',
            'editor': u'',
            'howpublished': u'',
            'institution': u'',
            'journal': u'',
            'keyField': u'',
            'month': u'',
            'note': u'',
            'number': u'',
            'organization': u'',
            'pages': u'',
            'publisher': u'',
            'school': u'',
            'series': u'',
            'title': u'',
            'typeField': u'',
            'url': u'',
            'volume': u'',
            'year': u'',
            'affiliation': u'',
            'abstract': u'',
            'contents': u'',
            'copyright': u'',
            'ISBN': u'',
            'ISSN': u'',
            'keywords': u'',
            'language': u'',
            'location': u'',
            'LCCN': u'',
            'mrnumber': u'',
            'price': u'',
            'size': u'',
        }
        self.speakerCreateParams = {
            'firstName': u'',
            'lastName': u'',
            'pageContent': u'',
            'dialect': u'dialect',
            'markupLanguage': u'reStructuredText'
        }
        self.syntacticCategoryCreateParams = {
            'name': u'',
            'type': u'',
            'description': u''
        }
        self.userCreateParams = {
            'username': u'',
            'password': u'',
            'password_confirm': u'',
            'firstName': u'',
            'lastName': u'',
            'email': u'',
            'affiliation': u'',
            'role': u'',
            'markupLanguage': u'',
            'pageContent': u'',
            'inputOrthography': None,
            'outputOrthography': None
        }

    def tearDown(self, **kwargs):
        clearAllTables = kwargs.get('clearAllTables', False)
        dirsToClear = kwargs.get('dirsToClear', [])
        delGlobalAppSet = kwargs.get('delGlobalAppSet', False)
        dirsToDestroy = kwargs.get('dirsToDestroy', [])

        if clearAllTables:
            h.clearAllTables(['language'])
        else:
            h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        for dirPath in dirsToClear:
            h.clearDirectoryOfFiles(getattr(self, dirPath))

        for dirName in dirsToDestroy:
            {
                'user': lambda: h.destroyAllDirectories('users', 'test.ini'),
                'corpus': lambda: h.destroyAllDirectories('corpora', 'test.ini'),
                'phonology': lambda: h.destroyAllDirectories('phonologies', 'test.ini'),
                'morphology': lambda: h.destroyAllDirectories('morphologies', 'test.ini'),
            }.get(dirName, lambda: None)()

        if delGlobalAppSet:
            # Perform a vacuous GET just to delete app_globals.applicationSettings
            # to clean up for subsequent tests.
            self.app.get(url('new_form'), extra_environ=self.extra_environ_admin_appset)

    def addSEARCHToWebTestValidMethods(self):
        """Hack to prevent webtest from printing warnings when SEARCH method is used."""
        new_valid_methods = list(webtest.lint.valid_methods)
        new_valid_methods.append('SEARCH')
        new_valid_methods = tuple(new_valid_methods)
        webtest.lint.valid_methods = new_valid_methods

def decompressGzipString(compressedData):
    compressedStream = StringIO.StringIO(compressedData)
    gzipFile = gzip.GzipFile(fileobj=compressedStream, mode="rb")
    return gzipFile.read()

def getFileSize(filePath):
    try:
        return os.path.getsize(filePath)
    except Exception:
        None

