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
from shutil import copyfileobj
from time import time
import simplejson as json
from time import sleep
from nose.tools import nottest
from sqlalchemy.sql import desc
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
from subprocess import call
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Morphology, MorphologyBackup

log = logging.getLogger(__name__)

class TestMorphologiesController(TestController):

    def tearDown(self):
        pass

    def createForm(self, tr, mb, mg, tl, cat):
        params = self.formCreateParams.copy()
        params.update({'transcription': tr, 'morphemeBreak': mb, 'morphemeGloss': mg,
            'translations': [{'transcription': tl, 'grammaticality': u''}], 'syntacticCategory': cat})
        params = json.dumps(params)
        self.app.post(url('forms'), params, self.json_headers, self.extra_environ_admin)

    #@nottest
    def test_a_create(self):
        """Tests that POST /morphologies creates a new morphology.

        """

        # Create the default application settings
        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add(applicationSettings)
        Session.commit()

        # Create some syntactic categories
        cats = {
            'N': model.SyntacticCategory(name=u'N'),
            'V': model.SyntacticCategory(name=u'V'),
            'AGR': model.SyntacticCategory(name=u'AGR'),
            'PHI': model.SyntacticCategory(name=u'PHI'),
            'S': model.SyntacticCategory(name=u'S'),
            'D': model.SyntacticCategory(name=u'D')
        }
        Session.add_all(cats.values())
        Session.commit()
        cats = dict([(k, v.id) for k, v in cats.iteritems()])


        dataset = (
            ('chien', 'chien', 'dog', 'dog', cats['N']),
            ('chat', 'chat', 'cat', 'cat', cats['N']),
            ('oiseau', 'oiseau', 'bird', 'bird', cats['N']),
            ('cheval', 'cheval', 'horse', 'horse', cats['N']),
            ('vache', 'vache', 'cow', 'cow', cats['N']),
            ('grenouille', 'grenouille', 'frog', 'frog', cats['N']),
            ('tortue', 'tortue', 'turtle', 'turtle', cats['N']),
            ('fourmi', 'fourmi', 'ant', 'ant', cats['N']),
            (u'be\u0301casse', u'be\u0301casse', 'woodcock', 'woodcock', cats['N']),

            ('parle', 'parle', 'speak', 'speak', cats['V']),
            ('grimpe', 'grimpe', 'climb', 'climb', cats['V']),
            ('nage', 'nage', 'swim', 'swim', cats['V']),
            ('tombe', 'tombe', 'fall', 'fall', cats['V']),

            ('le', 'le', 'the', 'the', cats['D']),
            ('la', 'la', 'the', 'the', cats['D']),

            ('s', 's', 'PL', 'plural', cats['PHI']),

            ('ait', 'ait', '3SG.IMPV', 'third person singular imperfective', cats['AGR']),
            ('aient', 'aient', '3PL.IMPV', 'third person plural imperfective', cats['AGR']),

            ('Les chiens nageaient.', 'le-s chien-s nage-aient', 'the-PL dog-PL swim-3PL.IMPV', 'The dogs were swimming.', cats['S']),
            ('La tortue parlait', 'la tortue parle-ait', 'the turtle speak-3SG.IMPV', 'The turtle was speaking.', cats['S'])
        )

        for tuple_ in dataset:
            self.createForm(*map(unicode, tuple_))

        # Create a lexicon form search and corpus
        query = {'filter': ['Form', 'syntacticCategory', 'name', 'in', [u'N', u'V', u'AGR', u'PHI', u'D']]}
        params = self.formSearchCreateParams.copy()
        params.update({
            'name': u'Find morphemes',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        lexiconFormSearchId = json.loads(response.body)['id']
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus of lexical items',
            'formSearch': lexiconFormSearchId
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        lexiconCorpusId = json.loads(response.body)['id']

        # Create a rules corpus
        query = {'filter': ['Form', 'syntacticCategory', 'name', '=', u'S']}
        params = self.formSearchCreateParams.copy()
        params.update({
            'name': u'Find sentences',
            'description': u'Returns all sentential forms',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        rulesFormSearchId = json.loads(response.body)['id']
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus of sentences',
            'formSearch': rulesFormSearchId
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        rulesCorpusId = json.loads(response.body)['id']

        # Create a rules corpus that contains no forms
        query = {'filter': ['Form', 'syntacticCategory', 'name', '=', u'NO EXISTY']}
        params = self.formSearchCreateParams.copy()
        params.update({
            'name': u'Find nothing',
            'description': u'Returns the empty set',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        emptyFormSearchId = json.loads(response.body)['id']
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus of nada',
            'formSearch': emptyFormSearchId
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        emptyRulesCorpusId = json.loads(response.body)['id']

        # Finally, create a morphology using the lexicon and rules corpora
        name = u'Morphology of a very small subset of french'
        params = self.morphologyCreateParams.copy()
        params.update({
            'name': name,
            'lexiconCorpus': lexiconCorpusId,
            'rulesCorpus': rulesCorpusId
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == name
        assert u'define morphology' in resp['script']
        assert u'(NCat)' in resp['script'] # cf. tortue
        assert u'(DCat)' in resp['script'] # cf. la
        assert u'(NCat "-" PHICat)' in resp['script'] # cf. chien-s
        assert u'(DCat "-" PHICat)' in resp['script'] # cf. le-s
        assert u'(VCat "-" AGRCat)' in resp['script'] # cf. nage-aient, parle-ait
        assert u'g r e n o u i l l e "%sfrog":0' % h.rareDelimiter in resp['script']
        assert u'b e \u0301 c a s s e "%swoodcock":0' % h.rareDelimiter in resp['script']

        # Attempt to create a morphology with no rules corpus and expect to fail
        params = self.morphologyCreateParams.copy()
        params.update({
            'name': u'Anonymous',
            'lexiconCorpus': 123456789
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin, 400)
        resp = json.loads(response.body)
        assert resp['errors']['rulesCorpus'] == u'Please enter a value'
        assert resp['errors']['lexiconCorpus'] == u'There is no corpus with id 123456789.'

        # Create a morphology with only a rules corpus
        params = self.morphologyCreateParams.copy()
        params.update({
            'name': u'Rules corpus only',
            'rulesCorpus': rulesCorpusId
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == u'Rules corpus only'
        assert u'define morphology' in resp['script']
        assert u'(NCat)' in resp['script'] # cf. tortue
        assert u'(DCat)' in resp['script'] # cf. la
        assert u'(NCat "-" PHICat)' in resp['script'] # cf. chien-s
        assert u'(DCat "-" PHICat)' in resp['script'] # cf. le-s
        assert u'(VCat "-" AGRCat)' in resp['script'] # cf. nage-aient, parle-ait
        # Note the change in the following two assertions from above.
        assert u'g r e n o u i l l e "%sfrog":0' % h.rareDelimiter not in resp['script']
        assert u'b e \u0301 c a s s e "%swoodcock":0' % h.rareDelimiter not in resp['script']

        # Create a morphology with only an empty rules corpus; this will generate an invalid
        # foma script, i.e., it will not compile.
        params = self.morphologyCreateParams.copy()
        params.update({
            'name': u'Empty rules corpus',
            'rulesCorpus': emptyRulesCorpusId
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['script'].replace(' ', '').replace('\n', '') == 'definemorphology();'

    #@nottest
    def test_b_index(self):
        """Tests that GET /morphologies returns all morphology resources.

        """

        morphologies = Session.query(Morphology).all()

        # Get all morphologies
        response = self.app.get(url('morphologies'), headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == 3

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 1, 'page': 1}
        response = self.app.get(url('morphologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['name'] == morphologies[0].name
        assert response.content_type == 'application/json'

        # Test the orderBy GET params.
        orderByParams = {'orderByModel': 'Morphology', 'orderByAttribute': 'id',
                     'orderByDirection': 'desc'}
        response = self.app.get(url('morphologies'), orderByParams,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == morphologies[-1].id
        assert response.content_type == 'application/json'

        # Test the orderBy *with* paginator.
        params = {'orderByModel': 'Morphology', 'orderByAttribute': 'id',
                     'orderByDirection': 'desc', 'itemsPerPage': 1, 'page': 3}
        response = self.app.get(url('morphologies'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert morphologies[0].name == resp['items'][0]['name']

        # Expect a 400 error when the orderByDirection param is invalid
        orderByParams = {'orderByModel': 'Morphology', 'orderByAttribute': 'name',
                     'orderByDirection': 'descending'}
        response = self.app.get(url('morphologies'), orderByParams, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['orderByDirection'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

    #@nottest
    def test_c_show(self):
        """Tests that GET /morphologies/id returns the morphology with id=id or an appropriate error."""

        morphologies = Session.query(Morphology).all()

        # Try to get a morphology using an invalid id
        id = 100000000000
        response = self.app.get(url('morphology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no morphology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('morphology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('morphology', id=morphologies[0].id), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == morphologies[0].name
        assert resp['description'] == morphologies[0].description
        assert resp['script'] == morphologies[0].script
        assert response.content_type == 'application/json'

    #@nottest
    def test_d_new_edit(self):
        """Tests that GET /morphologies/new and GET /morphologies/id/edit return the data needed to create or update a morphology.

        """

        morphologies = Session.query(Morphology).all()

        # Test GET /morphologies/new
        response = self.app.get(url('new_morphology'), headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp['corpora']) == 3

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_morphology', id=morphologies[0].id), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_morphology', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no morphology with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_morphology', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_morphology', id=morphologies[0].id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['morphology']['name'] == morphologies[0].name
        assert len(resp['data']['corpora']) == 3
        assert response.content_type == 'application/json'

    #@nottest
    def test_e_update(self):
        """Tests that PUT /morphologies/id updates the morphology with id=id."""

        morphologies = [json.loads(json.dumps(m, cls=h.JSONOLDEncoder))
            for m in Session.query(Morphology).all()]
        morphology1Id = morphologies[0]['id']
        morphology1Name = morphologies[0]['name']
        morphology1Modified = morphologies[0]['datetimeModified']
        morphology1Script = morphologies[0]['script']
        morphology1RulesCorpusId = morphologies[0]['rulesCorpus']['id']
        morphology1LexiconCorpusId = morphologies[0]['lexiconCorpus']['id']
        morphologyCount = len(morphologies)

        # Update the first morphology
        sleep(1)
        origBackupCount = Session.query(MorphologyBackup).count()
        params = self.morphologyCreateParams.copy()
        params.update({
            'name': morphology1Name,
            'description': u'New description',
            'rulesCorpus': morphology1RulesCorpusId,
            'lexiconCorpus': morphology1LexiconCorpusId
        })
        params = json.dumps(params)
        response = self.app.put(url('morphology', id=morphology1Id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        newBackupCount = Session.query(MorphologyBackup).count()
        datetimeModified = resp['datetimeModified']
        newMorphologyCount = Session.query(Morphology).count()
        assert morphologyCount == newMorphologyCount
        assert datetimeModified != morphology1Modified
        assert resp['description'] == u'New description'
        assert resp['script'] == morphology1Script
        assert response.content_type == 'application/json'
        assert origBackupCount + 1 == newBackupCount
        backup = Session.query(MorphologyBackup).filter(
            MorphologyBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(MorphologyBackup.id)).first()
        assert backup.datetimeModified.isoformat() == morphology1Modified
        assert backup.script == morphology1Script
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        response = self.app.put(url('morphology', id=morphology1Id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        morphologyCount = newMorphologyCount
        newMorphologyCount = Session.query(Morphology).count()
        ourMorphologyDatetimeModified = Session.query(Morphology).get(morphology1Id).datetimeModified
        assert ourMorphologyDatetimeModified.isoformat() == datetimeModified
        assert morphologyCount == newMorphologyCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Create a new sentential form that implies a new morphological rule: V-PHI
        S = Session.query(model.SyntacticCategory).filter(model.SyntacticCategory.name==u'S').first()
        formCreateParams = ('Les fourmis tombes.', 'le-s fourmi-s tombe-s', 'the-PL ant-PL fall-PL', 'The ants fallings.', S.id)
        self.createForm(*formCreateParams)

        # Another attempt at updating will still fail because the form just created will not have
        # updated the rules corpus of the morphology
        response = self.app.put(url('morphology', id=morphology1Id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        morphologyCount = newMorphologyCount
        newMorphologyCount = Session.query(Morphology).count()
        ourMorphologyDatetimeModified = Session.query(Morphology).get(morphology1Id).datetimeModified
        assert ourMorphologyDatetimeModified.isoformat() == datetimeModified
        assert morphologyCount == newMorphologyCount
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # However, if we now update the rules corpus, an otherwise vacuous update to the morphology will succeed
        rulesCorpus = Session.query(model.Corpus).get(morphology1RulesCorpusId)
        corpusCreateParams = self.corpusCreateParams.copy()
        corpusCreateParams.update({
            'name': rulesCorpus.name,
            'description': rulesCorpus.description,
            'content': rulesCorpus.content,
            'formSearch': rulesCorpus.formSearch.id
        })
        corpusCreateParams = json.dumps(corpusCreateParams)
        self.app.put(url('corpus', id=morphology1RulesCorpusId), corpusCreateParams, self.json_headers, self.extra_environ_admin)
        response = self.app.put(url('morphology', id=morphology1Id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        assert morphology1Script != resp['script']
        assert u'define morphology' in resp['script']
        assert u'(NCat)' in resp['script'] # cf. tortue
        assert u'(DCat)' in resp['script'] # cf. la
        assert u'(NCat "-" PHICat)' in resp['script'] # cf. chien-s
        assert u'(DCat "-" PHICat)' in resp['script'] # cf. le-s
        assert u'(VCat "-" AGRCat)' in resp['script'] # cf. nage-aient, parle-ait
        assert u'g r e n o u i l l e "%sfrog":0' % h.rareDelimiter in resp['script']
        assert u'b e \u0301 c a s s e "%swoodcock":0' % h.rareDelimiter in resp['script']
        assert u'(VCat "-" PHICat)' in resp['script'] # THIS IS THE NEW PART
        assert u'(VCat "-" PHICat)' not in morphology1Script # THIS IS THE NEW PART

    #@nottest
    def test_f_history(self):
        """Tests that GET /morphologies/id/history returns the morphology with id=id and its previous incarnations.

        The JSON object returned is of the form
        {'morphology': morphology, 'previousVersions': [...]}.

        """

        morphologies = Session.query(Morphology).all()
        morphology1Id = morphologies[0].id
        morphology1UUID = morphologies[0].UUID

        # Now get the history of the first morphology (which was updated twice in ``test_update``.
        response = self.app.get(
            url(controller='morphologies', action='history', id=morphology1Id),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'morphology' in resp
        assert 'previousVersions' in resp
        assert len(resp['previousVersions']) == 2

        # Get the same history as above, except use the UUID
        response = self.app.get(
            url(controller='morphologies', action='history', id=morphology1UUID),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'morphology' in resp
        assert 'previousVersions' in resp
        assert len(resp['previousVersions']) == 2

        # Attempt to get the history with an invalid id and expect to fail
        response = self.app.get(
            url(controller='morphologies', action='history', id=123456789),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset, status=404)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'No morphologies or morphology backups match 123456789'

        # Further tests could be done ... cf. the tests on the history action of the phonologies controller ...

    #@nottest
    def test_g_compile(self):
        """Tests that PUT /morphologies/id/compile compiles the foma script of the morphology with id.

        .. note::

            Morphology compilation is accomplished via a worker thread and
            requests to /morphologies/id/compile return immediately.  When the
            script compilation attempt has terminated, the values of the
            ``datetimeCompiled``, ``datetimeModified``, ``compileSucceeded``,
            ``compileMessage`` and ``modifier`` attributes of the morphology are
            updated.  Therefore, the tests must poll ``GET /morphologies/id``
            in order to know when the compilation-tasked worker has finished.

        .. note::

            Depending on system resources, the following tests may fail.  A fast
            system may compile the large FST in under 30 seconds; a slow one may
            fail to compile the medium one in under 30.

        Backups

        """
        morphologies = Session.query(Morphology).all()
        morphology1Id = morphologies[0].id

        # If foma is not installed, make sure the error message is being returned
        # and exit the test.
        if not h.fomaInstalled(forceCheck=True):
            response = self.app.put(url(controller='morphologies', action='compile',
                        id=morphology1Id), headers=self.json_headers,
                        extra_environ=self.extra_environ_contrib, status=400)
            resp = json.loads(response.body)
            assert resp['error'] == u'Foma and flookup are not installed.'
            return

        # Attempt to get the compiled script before it has been created.
        response = self.app.get(url(controller='morphologies', action='servecompiled',
            id=morphology1Id), headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'Morphology %d has not been compiled yet.' % morphology1Id

        # Compile the morphology's script
        morphologyDir = os.path.join(self.morphologiesPath, 'morphology_%d' % morphology1Id)
        morphologyBinaryFilename = 'morphology_%d.foma' % morphology1Id
        response = self.app.put(url(controller='morphologies', action='compile',
                    id=morphology1Id), headers=self.json_headers,
                    extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        datetimeCompiled = resp['datetimeCompiled']

        # Poll ``GET /morphologies/morphology1Id`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('morphology', id=morphology1Id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for morphology %d has terminated.' % morphology1Id)
                break
            else:
                log.debug('Waiting for morphology %d to compile ...' % morphology1Id)
            sleep(1)
        morphologyDirContents = os.listdir(morphologyDir)
        assert resp['compileSucceeded'] == True
        assert resp['compileMessage'] == u'Compilation process terminated successfully and new binary file was written.'
        assert morphologyBinaryFilename in morphologyDirContents
        assert resp['modifier']['role'] == u'contributor'

        # Get the compiled foma script.
        response = self.app.get(url(controller='morphologies', action='servecompiled',
            id=morphology1Id), headers=self.json_headers, extra_environ=self.extra_environ_admin)
        morphologyBinaryPath = os.path.join(self.morphologiesPath, 'morphology_%d' % morphology1Id,
               'morphology_%d.foma' % morphology1Id)
        fomaFile = open(morphologyBinaryPath, 'rb')
        fomaFileContent = fomaFile.read()
        assert fomaFileContent == response.body
        assert response.content_type == u'application/octet-stream'

        # Attempt to get the compiled foma script of a non-existent morphology.
        response = self.app.get(url(controller='morphologies', action='servecompiled',
            id=123456789), headers=self.json_headers,
            extra_environ=self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'There is no morphology with id 123456789'

        # Compile the first morphology's script again
        sleep(1.1)
        response = self.app.put(url(controller='morphologies', action='compile', id=morphology1Id),
                                headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyBinaryFilename = 'morphology_%d.foma' % morphology1Id
        morphologyDir = os.path.join(self.morphologiesPath, 'morphology_%d' % morphology1Id)
        datetimeCompiled = resp['datetimeCompiled']

        # Poll ``GET /morphologies/morphology1Id`` until ``datetimeCompiled`` has
        # changed.
        while True:
            response = self.app.get(url('morphology', id=morphology1Id),
                        headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            if datetimeCompiled != resp['datetimeCompiled']:
                log.debug('Compile attempt for morphology %d has terminated.' % morphology1Id)
                break
            else:
                log.debug('Waiting for morphology %d to compile ...' % morphology1Id)
            sleep(1)
        assert resp['compileSucceeded'] == True
        assert resp['compileMessage'] == u'Compilation process terminated successfully and new binary file was written.'
        assert morphologyBinaryFilename in os.listdir(morphologyDir)

        # Test that PUT /morphologies/id/applydown and PUT /morphologies/id/applyup are working correctly.
        # Note that the value of the ``transcriptions`` key can be a string or a list of strings.

        # Test applydown with a valid form|gloss-form|gloss sequence.
        morphemeSequence = u'chien%sdog-s%sPL' % (h.rareDelimiter, h.rareDelimiter)
        params = json.dumps({'morphemeSequences': morphemeSequence})
        response = self.app.put(url(controller='morphologies', action='applydown',
                    id=morphology1Id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % morphology1Id)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert resp[morphemeSequence] == ['chien-s']

        # Make sure the temporary morphologization files have been deleted.
        assert not [fn for fn in morphologyDirContents if fn.startswith('inputs_')]
        assert not [fn for fn in morphologyDirContents if fn.startswith('outputs_')]
        assert not [fn for fn in morphologyDirContents if fn.startswith('apply_')]

        # Test applydown with an invalid form|gloss-form|gloss sequence.
        invalidMorphemeSequence = u'e\u0301cureuil%ssquirrel-s%sPL' % (h.rareDelimiter, h.rareDelimiter)
        params = json.dumps({'morphemeSequences': invalidMorphemeSequence})
        response = self.app.put(url(controller='morphologies', action='applydown',
                    id=morphology1Id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % morphology1Id)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert resp[invalidMorphemeSequence] == [None]

        # Test applydown with multiple morpheme sequences.
        ms1 = u'chien%sdog-s%sPL' % (h.rareDelimiter, h.rareDelimiter)
        ms2 = u'tombe%sfall-s%sPL' % (h.rareDelimiter, h.rareDelimiter)
        params = json.dumps({'morphemeSequences': [ms1, ms2]})
        response = self.app.put(url(controller='morphologies', action='applydown',
                    id=morphology1Id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % morphology1Id)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert resp[ms1] == [u'chien-s']
        assert resp[ms2] == [u'tombe-s']

        # Test applyup
        morphemeSequence = u'chien-s'
        params = json.dumps({'morphemeSequences': morphemeSequence})
        response = self.app.put(url(controller='morphologies', action='applyup',
                    id=morphology1Id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % morphology1Id)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert resp[morphemeSequence] == ['chien%sdog-s%sPL' % (h.rareDelimiter, h.rareDelimiter)]

        # Test applyup with multiple input sequences
        ms1 = u'vache-s'
        ms2 = u'cheval'
        ms3 = u'vache-ait'
        ms4 = u'tombe-ait'
        params = json.dumps({'morphemeSequences': [ms1, ms2, ms3, ms4]})
        response = self.app.put(url(controller='morphologies', action='applyup',
                    id=morphology1Id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp[ms1] == ['vache%scow-s%sPL' % (h.rareDelimiter, h.rareDelimiter)]
        assert resp[ms2] == ['cheval%shorse' % h.rareDelimiter]
        assert resp[ms3] == [None]
        assert resp[ms4] == ['tombe%sfall-ait%s3SG.IMPV' % (h.rareDelimiter, h.rareDelimiter)]

    #@nottest
    def test_h_large_morphologies(self):
        """Tests that morphology functionality works with large datasets.

        .. note::

            This test only works if MySQL is being used as the RDBMS for the test
            *and* there is a file in 
            ``onlinelinguisticdatabase/onlinelinguisticdatabase/tests/data/datasets/``
            that is a MySQL dump file that drops, recreates and populates the form,
            formbackup, user, tag, elicitationmethod, syntacticcategory, source and
            translation tables.  The name of this file can be configured by setting 
            the ``olddumpfile`` variable.  Note that no such dump file is provided
            with the OLD source since the file used by the developer contains data
            that cannot be publicly shared.

        """

        # If foma is not installed, exit.
        if not h.fomaInstalled(forceCheck=True):
            return

        # Here we load a whole bunch of form (and auxiliary) data from the mysql dumpfile
        # in the tests/data/datesets directory.

        # The ``olddumpfile`` variable holds the name of a MySQL dump file in /tests/data/datasets
        # that will be used to populate the database.
        olddumpfile = 'blaold.sql'

        # The ``precompiled_morphology`` variable holds the name of a compiled foma script in /tests/data/morphologies
        # which should be the same file that is generated from the code below.  Specifying this file sidesteps the
        # lengthy compilation process, if desired.  Set this variable to None if you want the compilation.
        #precompiled_morphology = 'blaold_morphology.foma'
        precompiled_morphology = None

        olddumpfilePath = os.path.join(self.testDatasetsPath, olddumpfile)
        if not os.path.isfile(olddumpfilePath):
            return
        config = h.getConfig(configFilename='test.ini')
        SQLAlchemyURL = config['sqlalchemy.url']
        if not SQLAlchemyURL.split(':')[0] == 'mysql':
            return 
        rdbms, username, password, db_name = SQLAlchemyURL.split(':')
        username = username[2:]
        password = password.split('@')[0]
        db_name = db_name.split('/')[-1]
        tmpscriptPath = os.path.join(self.testDatasetsPath, 'tmp.sh')
        with open(tmpscriptPath, 'w') as tmpscript:
            tmpscript.write('#!/bin/sh\nmysql -u %s -p%s %s < %s' % (username, password, db_name, olddumpfilePath))
        os.chmod(tmpscriptPath, 0744)
        with open(os.devnull, "w") as fnull:
            call([tmpscriptPath], stdout=fnull, stderr=fnull)
        os.remove(tmpscriptPath)

        # Recreate the default users that the loaded dump file deleted
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        # Create a lexicon form search and corpus
        lexicalSynCatNames = ['nan', 'nin', 'nar', 'nir', 'vai', 'vii', 'vta', 'vti', 'vrt', 'adt', 'dem',
            'prev', 'med', 'fin', 'oth', 'o', 'und', 'pro', 'asp', 'ten', 'mod', 'agra', 'agrb', 'thm', 'whq',
            'num', 'drt', 'dim', 'stp', 'PN', 'INT']
        query = {'filter': ['Form', 'syntacticCategory', 'name', 'in', lexicalSynCatNames]}
        query_ = {'filter': ['and', [['Form', 'id', '<', 1000],
                                    ['Form', 'syntacticCategory', 'name', 'in', lexicalSynCatNames]]]}
        params = self.formSearchCreateParams.copy()
        params.update({
            'name': u'Blackfoot morphemes',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        lexiconFormSearchId = json.loads(response.body)['id']
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus of Blackfoot morphemes',
            'formSearch': lexiconFormSearchId
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        lexiconCorpusId = json.loads(response.body)['id']

        # Create a rules corpus
        query = {'filter': ['or', [['Form', 'syntacticCategory', 'name', '=', u'sent'],
                                   ['Form', 'transcription', 'like', '% %']]]}
        query_ = {'filter': ['and', [
                                ['or', [['Form', 'syntacticCategory', 'name', '=', u'sent'],
                                        ['Form', 'transcription', 'like', '% %']]],
                                ['Form', 'id', '<', 23000],
                                ['Form', 'id', '>', 22000]]]}
        params = self.formSearchCreateParams.copy()
        params.update({
            'name': u'Find Blackfoot sentences',
            'description': u'Returns all sentential forms',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        rulesFormSearchId = json.loads(response.body)['id']
        params = self.corpusCreateParams.copy()
        params.update({
            'name': u'Corpus of Blackfoot sentences',
            'formSearch': rulesFormSearchId
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        rulesCorpusId = json.loads(response.body)['id']

        # Finally, create a morphology using the lexicon and rules corpora
        name = u'Morphology of Blackfoot'
        params = self.morphologyCreateParams.copy()
        params.update({
            'name': name,
            'lexiconCorpus': lexiconCorpusId,
            'rulesCorpus': rulesCorpusId
        })
        params = json.dumps(params)
        t1 = time()
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin_appset)
        t2 = time()
        log.debug('Took %f seconds to create the morphology' % (t2 - t1))
        resp = json.loads(response.body)
        largeMorphologyId = resp['id']
        assert resp['name'] == name
        assert u'define morphology' in resp['script']

        # Compile the morphology's script
        morphologyDir = os.path.join(self.morphologiesPath, 'morphology_%d' % largeMorphologyId)
        morphologyBinaryFilename = 'morphology_%d.foma' % largeMorphologyId
        morphologyBinaryPath = os.path.join(morphologyDir, morphologyBinaryFilename)
        try:
            precompiled_morphology_path = os.path.join(self.testMorphologiesPath, precompiled_morphology)
        except Exception:
            precompiled_morphology_path = None
        if precompiled_morphology and precompiled_morphology_path and os.path.exists(precompiled_morphology_path):
            # Use the precompiled morphology script if it's available,
            copyfileobj(open(precompiled_morphology_path, 'rb'), open(morphologyBinaryPath, 'wb'))
        else:
            # Compile the morphology's script
            response = self.app.put(url(controller='morphologies', action='compile',
                        id=largeMorphologyId), headers=self.json_headers,
                        extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            datetimeCompiled = resp['datetimeCompiled']

            # Poll ``GET /morphologies/largeMorphologyId`` until ``datetimeCompiled`` has
            # changed.
            # WARNING: it takes about 7 minutes on my machine for foma to compile this morphology
            secondsElapsed = 0
            wait = 10
            while True:
                response = self.app.get(url('morphology', id=largeMorphologyId),
                            headers=self.json_headers, extra_environ=self.extra_environ_contrib)
                resp = json.loads(response.body)
                if datetimeCompiled != resp['datetimeCompiled']:
                    log.debug('Compile attempt for morphology %d has terminated.' % largeMorphologyId)
                    break
                else:
                    log.debug('Waiting for morphology %d to compile (%.2f minutes elapsed) ...' % (
                        largeMorphologyId, (secondsElapsed / 60.0)))
                sleep(wait)
                secondsElapsed = secondsElapsed + 10
            morphologyDirContents = os.listdir(morphologyDir)
            log.debug(morphologyDirContents)
            assert resp['compileSucceeded'] == True
            assert resp['compileMessage'] == u'Compilation process terminated successfully and new binary file was written.'
            assert morphologyBinaryFilename in morphologyDirContents
            assert resp['modifier']['role'] == u'contributor'

        # Get the compiled foma script.
        response = self.app.get(url(controller='morphologies', action='servecompiled',
            id=largeMorphologyId), headers=self.json_headers, extra_environ=self.extra_environ_admin)
        fomaFile = open(morphologyBinaryPath, 'rb')
        fomaFileContent = fomaFile.read()
        assert fomaFileContent == response.body
        assert response.content_type == u'application/octet-stream'

        # Test that PUT /morphologies/id/applydown and PUT /morphologies/id/applyup are working correctly.
        # Note that the value of the ``transcriptions`` key can be a string or a list of strings.
        seqs = (
            (
                u'ipommo%stransfer.title.to-oki%sINV-wa%s3SG' % (h.rareDelimiter, h.rareDelimiter, h.rareDelimiter),
                u'ipommo-oki-wa'
            ),
            (u'Joel%sJoel' % h.rareDelimiter, u'Joel'),
            (
                u'kit%s2-sska\u0301akanii%sagree' % (h.rareDelimiter, h.rareDelimiter),
                u'kit-sska\u0301akanii'
            )
        )

        # Test applydown with a valid morpheme sequence.
        params = json.dumps({'morphemeSequences': seqs[0][0]})
        response = self.app.put(url(controller='morphologies', action='applydown',
                    id=largeMorphologyId), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % largeMorphologyId)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert seqs[0][1] in resp[seqs[0][0]]

        # Make sure the temporary morphologization files have been deleted.
        assert not [fn for fn in morphologyDirContents if fn.startswith('inputs_')]
        assert not [fn for fn in morphologyDirContents if fn.startswith('outputs_')]
        assert not [fn for fn in morphologyDirContents if fn.startswith('apply_')]

        # Test applydown with an invalid form|gloss-form|gloss sequence.
        invalidMorphemeSequence = u'e\u0301cureuil%ssquirrel-s%sPL' % (h.rareDelimiter, h.rareDelimiter)
        params = json.dumps({'morphemeSequences': invalidMorphemeSequence})
        response = self.app.put(url(controller='morphologies', action='applydown',
                    id=largeMorphologyId), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % largeMorphologyId)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert resp[invalidMorphemeSequence] == [None]

        # Test applydown with multiple morpheme sequences.
        ms1 = seqs[0][0]
        ms2 = seqs[1][0]
        ms3 = seqs[2][0]
        params = json.dumps({'morphemeSequences': [ms1, ms2, ms3]})
        response = self.app.put(url(controller='morphologies', action='applydown',
                    id=largeMorphologyId), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % largeMorphologyId)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert seqs[0][1] in resp[ms1]
        assert seqs[1][1] in resp[ms2]
        assert seqs[2][1] in resp[ms3]

        # Test applyup
        params = json.dumps({'morphemeSequences': seqs[0][1]})
        response = self.app.put(url(controller='morphologies', action='applyup',
                    id=largeMorphologyId), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphologyDirPath = os.path.join(self.morphologiesPath,
                                        'morphology_%d' % largeMorphologyId)
        morphologyDirContents = os.listdir(morphologyDirPath)
        assert seqs[0][0] in resp[seqs[0][1]]

        # Test applyup with multiple input sequences
        params = json.dumps({'morphemeSequences': [seqs[0][1], seqs[1][1], seqs[2][1]]})
        response = self.app.put(url(controller='morphologies', action='applyup',
                    id=largeMorphologyId), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert seqs[0][0] in resp[seqs[0][1]]
        assert seqs[1][0] in resp[seqs[1][1]]
        assert seqs[2][0] in resp[seqs[2][1]]

    #@nottest
    def test_z_cleanup(self):
        """Clean up after the tests.

        """

        TestController.tearDown(
                self,
                clearAllTables=True,
                delGlobalAppSet=True,
                dirsToDestroy=['user', 'morphology', 'corpus'])
