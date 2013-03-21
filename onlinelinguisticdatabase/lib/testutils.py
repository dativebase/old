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

"""Utility functions, classes and constants for tests.

.. module:: testutils
   :synopsis: Utility functions, classes and constants for tests.

A number of functions, classes and constants used throughout the application's
tests.

"""

import StringIO
import gzip
import os

################################################################################
# Dicts of resource create/update parameters with valid defaults.
################################################################################

corpusCreateParams = {
    'name': u'',
    'description': u'',
    'content': u'',
    'formSearch': u'',
    'tags': []
}

fileCreateParams = {
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

formCreateParams = {
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

syntacticCategoryCreateParams = {
    'name': u'',
    'type': u'',
    'description': u''
}

def decompressGzipString(compressedData):
    compressedStream = StringIO.StringIO(compressedData)
    gzipFile = gzip.GzipFile(fileobj=compressedStream, mode="rb")
    return gzipFile.read()

def getFileSize(filePath):
    try:
        return os.path.getsize(filePath)
    except Exception:
        None

