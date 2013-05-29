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

"""oldterm helps you interact with an OLD application via the command line (terminal).

Usage:

1. Setup an OLD web service and begin serving it.

    $ cd old
    $ paster setup-app development.ini
    $ paster serve development.ini

2. Enter a Python prompt and import oldterm:

    $ python
    >>> import oldterm
    >>> old = oldterm.OLD('127.0.0.1', '5000')
    >>> old.login('username', 'password')
    True
    >>> forms = old.get('forms')

"""

import requests
import simplejson as json

class OLD(object):
    """Create an OLD instance to connect to a live OLD application."""
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.baseurl = 'http://%s:%s' % (host, port)
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def login(self, username, password):
        payload = json.dumps({'username': username, 'password': password})
        response = self.session.post('%s/login/authenticate' % self.baseurl, data=payload)
        return response.json().get('authenticated', False)

    def get(self, path, params=None):
        response = self.session.get('%s/%s' % (self.baseurl, path), params=params)
        return self.return_response(response)

    def post(self, path, data=json.dumps({})):
        response = self.session.post('%s/%s' % (self.baseurl, path), data=json.dumps(data))
        return self.return_response(response)

    def put(self, path, data=json.dumps({})):
        response = self.session.put('%s/%s' % (self.baseurl, path), data=json.dumps(data))
        return self.return_response(response)

    def delete(self, path, data=json.dumps({})):
        response = self.session.delete('%s/%s' % (self.baseurl, path), data=json.dumps(data))
        return self.return_response(response)

    def search(self, path, data):
        response = self.session.request('SEARCH', '%s/%s' % (self.baseurl, path), data=json.dumps(data))
        return self.return_response(response)

    def return_response(self, response):
        try:
            return response.json()
        except Exception:
            return response

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
        'status': u'tested',
        'date_elicited': u'',     # mm/dd/yyyy
        'syntax': u'',
        'semantics': u''
    }

def printform(form):
    """Print an OLD form to the terminal"""
    tmp = [('id', form['id'])]
    if form.get('narrow_phonetic_transcription', None): tmp.append(('NP', form['narrow_phonetic_transcription']))
    if form.get('phonetic_transcription', None): tmp.append(('BP', form['phonetic_transcription']))
    tmp.append(('TR', '%s%s' % (form['grammaticality'], form['transcription'])))
    if form.get('morpheme_break', None): tmp.append(('MB', form['morpheme_break']))
    if form.get('morpheme_gloss', None): tmp.append(('MG', form['morpheme_gloss']))
    tmp.append(('TL', ', '.join([u'\u2018%s\u2019' % tl['transcription'] for tl in form['translations']])))
    if form.get('syntactic_category_string', None): tmp.append(('SCS', form['syntactic_category_string']))
    if form.get('break_gloss_category', None): tmp.append(('BGC', form['break_gloss_category']))
    if form.get('syntactic_category', None): tmp.append(('SC', form['syntactic_category']['name']))
    print u'\n'.join([u'%-5s%s' % (u'%s:' % t[0], t[1]) for t in tmp])

class NTKOLD(OLD):
    """Subclass of the OLD that provides some Nata (NTK)-specific attributes.
    """
    orthography = [u'mb', u'nd', u'ng', u't', u'ch', u'h', u'k', u'm', u'n', u'ny',
        u"ng'", u'r', u'bh', u's', u'sh', u'gh', u'w', u'y', u'i', u'i\u0301', u'u',
        u'u\u0301', u'e', u'e\u0301', u'o', u'o\u0301', u'e\u0323', u'e\u0323\u0301',
        u'o\u0323', u'o\u0323\u0301', u'a', u'a\u0301']
    C = [u'mb', u'nd', u'ng', u't', u'ch', u'h', u'k', u'm', u'n', u'ny',
        u"ng'", u'r', u'bh', u's', u'sh', u'gh', u'w', u'y']
    C = u'(%s)' % u'|'.join(C)
    V = [u'i', u'i\u0301', u'u', u'u\u0301', u'e', u'e\u0301', u'o', u'o\u0301',
        u'e\u0323', u'e\u0323\u0301', u'o\u0323', u'o\u0323\u0301', u'a', u'a\u0301']
    V = u'(%s)' % u'|'.join(V)
    H = [u'i\u0301', u'u\u0301', u'e\u0301', u'o\u0301',
        u'e\u0323\u0301', u'o\u0323\u0301', u'a\u0301']
    H = u'(%s)' % u'|'.join(H)
    L = u'(%s)' % u'|'.join([u'i', u'u', u'e', u'o', u'e\u0323', u'o\u0323'])
    CV = u'%s%s' % (C, V)
    CVV = u'%s%s' % (CV, V)
    CH = u'%s%s' % (C, H)
    CL = u'%s%s' % (C, L)

    # Find all forms that are CVV morphemes
    CVV_m = '^%s$' % CVV

    # Find all forms containing words that are CL.CL.CH
    CLCLCH_w = '(^| )%s%s%s($| )' % (CL, CL, CH)

    # Find all forms containing morphemes of the form GREEK LETTER BETA followed by "u"
    # i.e., PASS or C14
    bu_m = u'-\u03b2u(-| |$)'

    # Find all forms containing morphemes of the form GREEK LETTER BETA followed by "u"
    # i.e., PASS or C14
    PASS_m = u'-PASS(-| |$)'

    # Find all /Bu/ 'PASS' forms
    bu_PASS_m = ur'-\u03b2u\|PASS\|[^-]+(-| |$)'
