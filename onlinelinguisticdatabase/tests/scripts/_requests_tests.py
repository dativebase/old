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
r_JSON = r.json()
error_msg = 'Unable to get users.'
assert r.headers['Content-Type'] == 'application/json', error_msg
assert type(r_JSON) == list, error_msg
assert len(r_JSON) > 0, error_msg
assert u'Admin' in [u.get('first_name') for u in r_JSON], error_msg 

# Request GET /forms.
r = s.get('%s/forms' % baseurl)
assert type(r.json()) == list, 'Could not GET /forms.'

# Request POST /forms to create a form.
form_create_params = {
    'transcription': u'',
    'phonetic_transcription': u'',
    'narrow_phonetic_transcription': u'',
    'morpheme_break': u'',
    'grammaticality': u'',
    'morpheme_gloss': u'',
    'translations': [],
    'comments': u'',
    'speaker_comments': u'',
    'elicitation_method': u'',
    'tags': [],
    'syntactic_category': u'',
    'speaker': u'',
    'elicitor': u'',
    'verifier': u'',
    'source': u'',
    'status': u'',
    'date_elicited': u''     # mm/dd/yyyy
}

# First attempt to create a form with invalid params.
payload = form_create_params.copy()
payload['transcription'] = u'test'
r = s.post('%s/forms' % baseurl, data=json.dumps(payload))
r_JSON = r.json()
error_msg = u'Failed in attempt to request creation of an invalid form.'
assert r.status_code == 400, error_msg
assert r_JSON.get('errors', {}).get('translations') == u'Please enter a value', error_msg

# Create a valid form.
payload['translations'].append({'transcription': u'test', 'grammaticality': u''})
r = s.post('%s/forms' % baseurl, data=json.dumps(payload))
r_JSON = r.json()
error_msg = u'Failed in attempt to request creation of a form.'
try:
    form_id = r_JSON.get('id')
except:
    print r_JSON
assert r.status_code == 200, error_msg
assert r_JSON.get('transcription') == u'test'
assert r_JSON.get('translations', {'transcription': None})[0]['transcription'] == u'test'

# Request GET /forms/id and expect to receive the form we just created.
r = s.get('%s/forms/%s' % (baseurl, form_id))
r_JSON = r.json()
error_msg = 'Error: unable to retrieve the form just created.'
assert type(r_JSON) == dict, error_msg
assert r_JSON.get('transcription') == u'test', error_msg

# Ensure that @h.restrict is returning JSON
r = s.post('%s/forms/history/1' % baseurl)
error_msg = '@h.restrict not working as expected.'
assert r.status_code == 405, error_msg
assert r.json().get('error') == u"The POST method is not permitted for this resource; permitted method(s): GET", error_msg

# Ensure that invalid URLs return JSON also
r = s.put('%s/files' % baseurl)
error_msg = 'Invalid URLs are not returning JSON.'
assert r.status_code == 404, error_msg
assert r.json().get('error') == u'The resource could not be found.', error_msg

print 'All requests tests passed.'
