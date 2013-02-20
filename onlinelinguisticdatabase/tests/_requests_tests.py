#!/usr/bin/python

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

"""This script uses the Python Requests library to run some basic tests on a
live OLD web service.

Usage:

1. Setup an OLD web service and begin serving it.

    $ cd old
    $ paster setup-app development.ini
    $ paster serve development.ini

2. Run the requests script and expect not to see (assertion) errors:

    $ ./onlinelinguisticdatabase/tests/requests_tests.py

Note that the above command will only work if the requests module is installed
in the Python referenced at /usr/bin.  If you are using a virtual environment,
run the following command instead:

    $ env/bin/python onlinelinguisticdatabase/tests/requests_tests.py

"""

import requests
import simplejson as json
import os
from time import sleep

host = '127.0.0.1'
port = '5000'
baseurl = 'http://%s:%s' % (host, port)

s = requests.Session()
s.headers.update({'Content-Type': 'application/json'})

# Request authentication.
payload = json.dumps({'username': u'admin', 'password': u'adminA_1'})
r = s.post('%s/login/authenticate' % baseurl, data=payload)
assert r.json().get('authenticated') == True, 'Authentication failed.'

# Now that we're authenticated, get the default users.
r = s.get('%s/users' % baseurl)
rJSON = r.json()
errorMsg = 'Unable to get users.'
assert r.headers['Content-Type'] == 'application/json', errorMsg
assert type(rJSON) == list, errorMsg
assert len(rJSON) > 0, errorMsg
assert u'Admin' in [u.get('firstName') for u in rJSON], errorMsg 

# Request GET /forms.
r = s.get('%s/forms' % baseurl)
assert type(r.json()) == list, 'Could not GET /forms.'

# Request POST /forms to create a form.
formCreateParams = {
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
    'status': u'',
    'dateElicited': u''     # mm/dd/yyyy
}

# First attempt to create a form with invalid params.
payload = formCreateParams.copy()
payload['transcription'] = u'test'
r = s.post('%s/forms' % baseurl, data=json.dumps(payload))
rJSON = r.json()
errorMsg = u'Failed in attempt to request creation of an invalid form.'
assert r.status_code == 400, errorMsg
assert rJSON.get('errors', {}).get('glosses') == u'Please enter a value', errorMsg

# Create a valid form.
payload['glosses'].append({'gloss': u'test', 'glossGrammaticality': u''})
r = s.post('%s/forms' % baseurl, data=json.dumps(payload))
rJSON = r.json()
errorMsg = u'Failed in attempt to request creation of a form.'
try:
    formId = rJSON.get('id')
except:
    print rJSON
assert r.status_code == 200, errorMsg
assert rJSON.get('transcription') == u'test'
assert rJSON.get('glosses', {'gloss': None})[0]['gloss'] == u'test'

# Request GET /forms/id and expect to receive the form we just created.
r = s.get('%s/forms/%s' % (baseurl, formId))
rJSON = r.json()
errorMsg = 'Error: unable to retrieve the form just created.'
assert type(rJSON) == dict, errorMsg
assert rJSON.get('transcription') == u'test', errorMsg

# Ensure that @h.restrict is returning JSON
r = s.post('%s/forms/history/1' % baseurl)
errorMsg = '@h.restrict not working as expected.'
assert r.status_code == 405, errorMsg
assert r.json().get('error') == u"The POST method is not permitted for this resource; permitted method(s): GET", errorMsg

# Ensure that invalid URLs return JSON also
r = s.put('%s/files' % baseurl)
errorMsg = 'Invalid URLs are not returning JSON.'
assert r.status_code == 404, errorMsg
assert r.json().get('error') == u'The resource could not be found.', errorMsg

print 'All requests tests passed.'
