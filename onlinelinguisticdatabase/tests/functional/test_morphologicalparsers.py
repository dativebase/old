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
import sys
import codecs
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

class TestMorphologicalparsersController(TestController):
    """Tests the morphologicalparsers controller.  WARNING: the tests herein are pretty messy.  The higher 
    ordered tests will fail if the previous tests have not been run.

    """

    def __init__(self, *args, **kwargs):
        TestController.__init__(self, *args, **kwargs)
        self.blackfoot_phonology_script = h.normalize(
            codecs.open(self.test_phonology_script_path, 'r', 'utf8').read())

    def tearDown(self):
        pass

    def create_form(self, tr, mb, mg, tl, cat):
        params = self.form_create_params.copy()
        params.update({'transcription': tr, 'morpheme_break': mb, 'morpheme_gloss': mg,
            'translations': [{'transcription': tl, 'grammaticality': u''}], 'syntactic_category': cat})
        params = json.dumps(params)
        self.app.post(url('forms'), params, self.json_headers, self.extra_environ_admin)

    def human_readable_seconds(self, seconds):
        return u'%02dm%02ds' % (seconds / 60, seconds % 60)

    @nottest
    def test(self):
        """General purpose test for morphological parsers.
        """

        # Create the default application settings -- note that we have only one morpheme delimiter.
        # This is relevant to the morphemic language model.
        application_settings = h.generate_default_application_settings()
        application_settings.morpheme_delimiters = u'-'
        Session.add(application_settings)
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
            ('poule!t', 'poule!t', 'chicken', 'chicken', cats['N']), # note the ! which is a foma reserved symbol
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

            ('Les chats nageaient.', 'le-s chat-s nage-aient', 'the-PL cat-PL swim-3PL.IMPV', 'The cats were swimming.', cats['S']),
            ('La tortue parlait', 'la tortue parle-ait', 'the turtle speak-3SG.IMPV', 'The turtle was speaking.', cats['S'])
        )

        for tuple_ in dataset:
            self.create_form(*map(unicode, tuple_))

        # Create a form search model that returns lexical items (will be used to create the lexicon corpus)
        query = {'filter': ['Form', 'syntactic_category', 'name', 'in', [u'N', u'V', u'AGR', u'PHI', u'D']]}
        params = self.form_search_create_params.copy()
        params.update({
            'name': u'Find morphemes',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        lexicon_form_search_id = json.loads(response.body)['id']

        # Create the lexicon corpus
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of lexical items',
            'form_search': lexicon_form_search_id
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        lexicon_corpus_id = json.loads(response.body)['id']

        # Create a form search model that returns sentences (will be used to create the rules corpus)
        query = {'filter': ['Form', 'syntactic_category', 'name', '=', u'S']}
        params = self.form_search_create_params.copy()
        params.update({
            'name': u'Find sentences',
            'description': u'Returns all sentential forms',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        rules_form_search_id = json.loads(response.body)['id']

        # Create the rules corpus
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of sentences',
            'form_search': rules_form_search_id
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        rules_corpus_id = json.loads(response.body)['id']

        # Create a morphology using the lexicon and rules corpora
        name = u'Morphology of a very small subset of french'
        params = self.morphology_create_params.copy()
        params.update({
            'name': name,
            'lexicon_corpus': lexicon_corpus_id,
            'rules_corpus': rules_corpus_id,
            'script_type': 'regex'
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphology_id = resp['id']
        assert resp['name'] == name
        assert resp['script_type'] == u'regex'

        # If foma is not installed, make sure the error message is being returned
        # and exit the test.
        if not h.foma_installed(force_check=True):
            response = self.app.put(url(controller='morphologies', action='generate_and_compile',
                        id=morphology_id), headers=self.json_headers,
                        extra_environ=self.extra_environ_contrib, status=400)
            resp = json.loads(response.body)
            assert resp['error'] == u'Foma and flookup are not installed.'
            return

        # Compile the morphology's script
        response = self.app.put(url(controller='morphologies', action='generate_and_compile',
                    id=morphology_id), headers=self.json_headers,
                    extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        compile_attempt = resp['compile_attempt']

        # Poll ``GET /morphologies/morphology_id`` until ``compile_attempt`` has changed.
        while True:
            response = self.app.get(url('morphology', id=morphology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for morphology %d has terminated.' % morphology_id)
                break
            else:
                log.debug('Waiting for morphology %d to compile ...' % morphology_id)
            sleep(1)
        response = self.app.get(url('morphology', id=morphology_id), params={'script': u'1', 'lexicon': u'1'},
                    headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        morphology_dir = os.path.join(self.morphologies_path, 'morphology_%d' % morphology_id)
        morphology_binary_filename = 'morphology_%d.foma' % morphology_id
        morphology_dir_contents = os.listdir(morphology_dir)
        morphology_script_path = os.path.join(morphology_dir, 'morphology_%d.script' % morphology_id)
        morphology_script = codecs.open(morphology_script_path, mode='r', encoding='utf8').read()
        assert u'define morphology' in morphology_script
        assert u'(NCat)' in morphology_script # cf. tortue
        assert u'(DCat)' in morphology_script # cf. la
        assert u'(NCat "-" PHICat)' in morphology_script # cf. chien-s
        assert u'(DCat "-" PHICat)' in morphology_script # cf. le-s
        assert u'(VCat "-" AGRCat)' in morphology_script # cf. nage-aient, parle-ait
        assert u'c h a t "%scat":0' % h.rare_delimiter in morphology_script # cf. extract_morphemes_from_rules_corpus = False and chat's exclusion from the lexicon corpus
        assert u'c h i e n "%sdog":0' % h.rare_delimiter in morphology_script
        assert u'b e \u0301 c a s s e "%swoodcock":0' % h.rare_delimiter in morphology_script
        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert morphology_binary_filename in morphology_dir_contents
        assert resp['modifier']['role'] == u'contributor'
        rules = resp['rules']
        assert u'D' in rules # cf. le
        assert u'N' in rules # cf. tortue
        assert u'D-PHI' in rules # cf. le-s
        assert u'N-PHI' in rules # cf. chien-s
        assert u'V-AGR' in rules # cf. nage-aient, parle-ait
        assert 'lexicon' in resp
        assert 'script' in resp
        assert resp['script'] == morphology_script
        assert [u'chat', u'cat'] in resp['lexicon']['N']
        assert [u'chien', u'dog'] in resp['lexicon']['N']

        # Test GET /morphologies/1?script=1&lexicon=1 and make sure the script and lexicon are returned
        response = self.app.get(url('morphology', id=morphology_id), params={'script': u'1', 'lexicon': u'1'},
                    headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp['script'] == morphology_script
        lexicon = resp['lexicon']
        assert ['s', 'PL'] in lexicon['PHI']
        assert ['oiseau', 'bird'] in lexicon['N']
        assert ['aient', '3PL.IMPV'] in lexicon['AGR']
        assert ['la', 'the'] in lexicon['D']
        assert ['nage', 'swim'] in lexicon['V']

        # Create a very simple French phonology
        script = u'''
define eDrop e -> 0 || _ "-" a;
define breakDrop "-" -> 0;
define phonology eDrop .o. breakDrop;
        '''
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Phonology',
            'description': u'Covers a lot of the data.',
            'script': script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_id = resp['id']

        # Create a morphological parser for toy french
        params = self.morphological_parser_create_params.copy()
        params.update({
            'name': u'Morphological parser for toy French',
            'phonology': phonology_id,
            'morphology': morphology_id,
            'language_model': rules_corpus_id
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologicalparsers'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphological_parser_id = resp['id']

        # Generate the parser's morphophonology FST, compile it and generate the morphemic language model
        response = self.app.put(url(controller='morphologicalparsers', action='generate_and_compile',
            id=morphological_parser_id), headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        morphological_parser_compile_attempt = resp['compile_attempt']
        log.debug(resp)

        # Poll ``GET /morphologicalparsers/morphological_parser_id`` until ``compile_attempt`` has changed.
        while True:
            response = self.app.get(url('morphologicalparser', id=morphological_parser_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if morphological_parser_compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for morphological parser %d has terminated.' % morphological_parser_id)
                break
            else:
                log.debug('Waiting for morphological parser %d to compile ...' % morphological_parser_id)
            sleep(1)
        log.debug(resp)

    @nottest
    def test_c_index(self):
        """Tests that GET /morphologies returns all morphology resources."""

        morphologies = Session.query(Morphology).all()

        # Get all morphologies
        response = self.app.get(url('morphologies'), headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == 3

        # Test the paginator GET params.
        paginator = {'items_per_page': 1, 'page': 1}
        response = self.app.get(url('morphologies'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['name'] == morphologies[0].name
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'Morphology', 'order_by_attribute': 'id',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('morphologies'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == morphologies[-1].id
        assert response.content_type == 'application/json'

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'Morphology', 'order_by_attribute': 'id',
                     'order_by_direction': 'desc', 'items_per_page': 1, 'page': 3}
        response = self.app.get(url('morphologies'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert morphologies[0].name == resp['items'][0]['name']

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'Morphology', 'order_by_attribute': 'name',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('morphologies'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

    @nottest
    def test_d_show(self):
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
        assert response.content_type == 'application/json'

    @nottest
    def test_e_new_edit(self):
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

    @nottest
    def test_f_update(self):
        """Tests that PUT /morphologies/id updates the morphology with id=id."""

        foma_installed = h.foma_installed(force_check=True)

        morphologies = [json.loads(json.dumps(m, cls=h.JSONOLDEncoder))
            for m in Session.query(Morphology).all()]
        morphology_id = morphologies[0]['id']
        morphology_1_name = morphologies[0]['name']
        morphology_1_description = morphologies[0]['description']
        morphology_1_modified = morphologies[0]['datetime_modified']
        morphology_1_rules_corpus_id = morphologies[0]['rules_corpus']['id']
        morphology_1_lexicon_corpus_id = morphologies[0]['lexicon_corpus']['id']
        morphology_count = len(morphologies)
        morphology_1_dir = os.path.join(self.morphologies_path, 'morphology_%d' % morphology_id)
        morphology_1_script_path = os.path.join(morphology_1_dir, 'morphology_%d.script' % morphology_id)
        morphology_1_script = u''
        if foma_installed:
            morphology_1_script = codecs.open(morphology_1_script_path, mode='r', encoding='utf8').read()

        # Update the first morphology.  This will create the second backup for this morphology,
        # the first having been created by the successful compile attempt in test_compile.
        original_backup_count = Session.query(MorphologyBackup).count()
        params = self.morphology_create_params.copy()
        params.update({
            'name': morphology_1_name,
            'description': u'New description',
            'rules_corpus': morphology_1_rules_corpus_id,
            'lexicon_corpus': morphology_1_lexicon_corpus_id,
            'script_type': u'regex'
        })
        params = json.dumps(params)
        response = self.app.put(url('morphology', id=morphology_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        new_backup_count = Session.query(MorphologyBackup).count()
        datetime_modified = resp['datetime_modified']
        new_morphology_count = Session.query(Morphology).count()
        if foma_installed:
            updated_morphology_1_script = codecs.open(morphology_1_script_path, mode='r', encoding='utf8').read()
        else:
            updated_morphology_1_script = u''
        assert morphology_count == new_morphology_count
        assert datetime_modified != morphology_1_modified
        assert resp['description'] == u'New description'
        assert updated_morphology_1_script == morphology_1_script
        assert response.content_type == 'application/json'
        assert original_backup_count + 1 == new_backup_count
        backup = Session.query(MorphologyBackup).filter(
            MorphologyBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(MorphologyBackup.id)).first()
        assert backup.datetime_modified.isoformat() == morphology_1_modified
        assert backup.description == morphology_1_description
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        response = self.app.put(url('morphology', id=morphology_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        morphology_count = new_morphology_count
        new_morphology_count = Session.query(Morphology).count()
        our_morphology_datetime_modified = Session.query(Morphology).get(morphology_id).datetime_modified
        assert our_morphology_datetime_modified.isoformat() == datetime_modified
        assert morphology_count == new_morphology_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Create a new sentential form that implies a new morphological rule: V-PHI
        S = Session.query(model.SyntacticCategory).filter(model.SyntacticCategory.name==u'S').first()
        form_create_params = ('Les fourmis tombes.', 'le-s fourmi-s tombe-s', 'the-PL ant-PL fall-PL', 'The ants fallings.', S.id)
        self.create_form(*form_create_params)

        # Another attempt at updating will still fail because the form just created will not have
        # updated the rules corpus of the morphology
        response = self.app.put(url('morphology', id=morphology_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        morphology_count = new_morphology_count
        new_morphology_count = Session.query(Morphology).count()
        our_morphology_datetime_modified = Session.query(Morphology).get(morphology_id).datetime_modified
        assert our_morphology_datetime_modified.isoformat() == datetime_modified
        assert morphology_count == new_morphology_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

        # Now update the rules corpus
        rules_corpus = Session.query(model.Corpus).get(morphology_1_rules_corpus_id)
        corpus_create_params = self.corpus_create_params.copy()
        corpus_create_params.update({
            'name': rules_corpus.name,
            'description': rules_corpus.description,
            'content': rules_corpus.content,
            'form_search': rules_corpus.form_search.id
        })
        corpus_create_params = json.dumps(corpus_create_params)
        self.app.put(url('corpus', id=morphology_1_rules_corpus_id), corpus_create_params, self.json_headers, self.extra_environ_admin)

        # If we now perform a compile request on the morphology, we will get an updated script.
        # This will also result in the generation of a new morphology backup.
        if h.foma_installed(force_check=True):
            response = self.app.put(url(controller='morphologies', action='generate_and_compile',
                        id=morphology_id), headers=self.json_headers,
                        extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            compile_attempt = resp['compile_attempt']
            while True:
                response = self.app.get(url('morphology', id=morphology_id),
                            headers=self.json_headers, extra_environ=self.extra_environ_contrib)
                resp = json.loads(response.body)
                if compile_attempt != resp['compile_attempt']:
                    log.debug('Compile attempt for morphology %d has terminated.' % morphology_id)
                    break
                else:
                    log.debug('Waiting for morphology %d to compile ...' % morphology_id)
                sleep(1)
            updated_morphology_1_script = codecs.open(morphology_1_script_path, mode='r', encoding='utf8').read()
            assert morphology_1_script != updated_morphology_1_script
            assert u'define morphology' in updated_morphology_1_script
            assert u'(NCat)' in updated_morphology_1_script # cf. tortue
            assert u'(DCat)' in updated_morphology_1_script # cf. la
            assert u'(NCat "-" PHICat)' in updated_morphology_1_script # cf. chien-s
            assert u'(DCat "-" PHICat)' in updated_morphology_1_script # cf. le-s
            assert u'(VCat "-" AGRCat)' in updated_morphology_1_script # cf. nage-aient, parle-ait
            assert u'c h i e n "%sdog":0' % h.rare_delimiter in updated_morphology_1_script
            assert u'b e \u0301 c a s s e "%swoodcock":0' % h.rare_delimiter in updated_morphology_1_script
            assert u'(VCat "-" PHICat)' in updated_morphology_1_script # THIS IS THE NEW PART
            assert u'(VCat "-" PHICat)' not in morphology_1_script # THIS IS THE NEW PART

    @nottest
    def test_g_history(self):
        """Tests that GET /morphologies/id/history returns the morphology with id=id and its previous incarnations.

        The JSON object returned is of the form
        {'morphology': morphology, 'previous_versions': [...]}.

        """

        foma_installed = h.foma_installed(force_check=True)
        if foma_installed:
            # Note: compilation requests no longer result in the creation of backups.
            # Ignore the above assertions that they do.
            morphology_1_backup_count = 2
        else:
            morphology_1_backup_count = 1

        morphologies = Session.query(Morphology).all()
        morphology_id = morphologies[0].id
        morphology_1_UUID = morphologies[0].UUID

        # Now get the history of the first morphology (which was updated twice in ``test_update``.
        response = self.app.get(
            url(controller='morphologies', action='history', id=morphology_id),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'morphology' in resp
        assert 'previous_versions' in resp
        assert len(resp['previous_versions']) == morphology_1_backup_count
        if foma_installed:
            assert resp['previous_versions'][0]['extract_morphemes_from_rules_corpus'] == True
            assert resp['previous_versions'][1]['extract_morphemes_from_rules_corpus'] == False

        # Get the same history as above, except use the UUID
        response = self.app.get(
            url(controller='morphologies', action='history', id=morphology_1_UUID),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'morphology' in resp
        assert 'previous_versions' in resp
        assert len(resp['previous_versions']) == morphology_1_backup_count

        # Attempt to get the history with an invalid id and expect to fail
        response = self.app.get(
            url(controller='morphologies', action='history', id=123456789),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset, status=404)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'No morphologies or morphology backups match 123456789'

        # Further tests could be done ... cf. the tests on the history action of the phonologies controller ...

    @nottest
    def test_h_lexc_scripts(self):
        """Tests that morphologies written in the lexc formalism work as expected."""

        if not h.foma_installed(force_check=True):
            return

        morphologies = [json.loads(json.dumps(m, cls=h.JSONOLDEncoder))
            for m in Session.query(Morphology).all()]
        morphology_id = morphologies[0]['id']
        morphology_1_name = morphologies[0]['name']
        morphology_1_description = morphologies[0]['description']
        morphology_1_modified = morphologies[0]['datetime_modified']
        morphology_1_compile_attempt = morphologies[0]['compile_attempt']
        morphology_1_rules_corpus_id = morphologies[0]['rules_corpus']['id']
        morphology_1_lexicon_corpus_id = morphologies[0]['lexicon_corpus']['id']
        morphology_count = len(morphologies)
        morphology_1_dir = os.path.join(self.morphologies_path, 'morphology_%d' % morphology_id)
        morphology_1_script_path = os.path.join(morphology_1_dir, 'morphology_%d.script' % morphology_id)
        morphology_1_script = codecs.open(morphology_1_script_path, mode='r', encoding='utf8').read()

        # Update morphology 1 by making it into a lexc script
        orig_backup_count = Session.query(MorphologyBackup).count()
        params = self.morphology_create_params.copy()
        params.update({
            'name': morphology_1_name,
            'description': morphology_1_description,
            'rules_corpus': morphology_1_rules_corpus_id,
            'lexicon_corpus': morphology_1_lexicon_corpus_id,
            'script_type': u'lexc'
        })
        params = json.dumps(params)
        response = self.app.put(url('morphology', id=morphology_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        new_backup_count = Session.query(MorphologyBackup).count()
        datetime_modified = resp['datetime_modified']
        new_morphology_count = Session.query(Morphology).count()
        assert new_backup_count == orig_backup_count + 1
        assert new_morphology_count == morphology_count
        assert resp['script_type'] == u'lexc'
        assert datetime_modified > morphology_1_modified

        # Before we compile, save the previous script and its compiled version, just for testing
        # NOTE: I compared the compiled regexes generated from the two different types of scripts
        # generated for the same morphology: foma did *not* evaluate them as equivalent.  I do not know
        # what to make of this at this point ...
        morphology_path = os.path.join(self.morphologies_path, 'morphology_%d' % morphology_id)
        #morphology_script_path = os.path.join(morphology_path, 'morphology_%d.script' % morphology_id)
        #morphology_script_backup_path = os.path.join(morphology_path, 'morphology_%d_backup.script' % morphology_id)
        morphology_binary_path = os.path.join(morphology_path, 'morphology_%d.foma' % morphology_id)
        #morphology_binary_backup_path = os.path.join(morphology_path, 'morphology_%d_backup.foma' % morphology_id)
        #copyfileobj(open(morphology_script_path, 'rb'), open(morphology_script_backup_path, 'wb'))
        #copyfileobj(open(morphology_binary_path, 'rb'), open(morphology_binary_backup_path, 'wb'))

        # Compile the morphology and get an altogether new script, i.e., one in the lexc formalism this time
        response = self.app.put(url(controller='morphologies', action='generate_and_compile',
                    id=morphology_id), headers=self.json_headers,
                    extra_environ=self.extra_environ_contrib)

        # Poll ``GET /morphologies/morphology_id`` until ``compile_attempt`` has changed.
        while True:
            response = self.app.get(url('morphology', id=morphology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if morphology_1_compile_attempt != resp['compile_attempt']:
                log.debug('Compile attempt for morphology %d has terminated.' % morphology_id)
                break
            else:
                log.debug('Waiting for morphology %d to compile ...' % morphology_id)
            sleep(1)

        updated_morphology_1_script = codecs.open(morphology_1_script_path, mode='r', encoding='utf8').read()
        assert updated_morphology_1_script != morphology_1_script
        assert resp['compile_succeeded'] == True
        assert resp['compile_message'] == u'Compilation process terminated successfully and new binary file was written.'
        assert u'define morphology' not in updated_morphology_1_script
        assert u'define morphology' in morphology_1_script
        assert resp['modifier']['role'] == u'contributor'

        # Get the compiled foma script.
        response = self.app.get(url(controller='morphologies', action='servecompiled',
            id=morphology_id), headers=self.json_headers, extra_environ=self.extra_environ_admin)
        foma_file = open(morphology_binary_path, 'rb')
        foma_file_content = foma_file.read()
        assert foma_file_content == response.body
        assert response.content_type == u'application/octet-stream'

        # Test applydown with multiple morpheme sequences.
        ms1 = u'chien%sdog-s%sPL' % (h.rare_delimiter, h.rare_delimiter)
        ms2 = u'tombe%sfall-s%sPL' % (h.rare_delimiter, h.rare_delimiter)
        ms3 = u'e\u0301cureuil%ssquirrel-s%sPL' % (h.rare_delimiter, h.rare_delimiter)
        params = json.dumps({'morpheme_sequences': [ms1, ms2, ms3]})
        response = self.app.put(url(controller='morphologies', action='applydown',
                    id=morphology_id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp[ms1] == [u'chien-s']
        assert resp[ms2] == [u'tombe-s']
        assert resp[ms3] == [None]

        # Test applyup with multiple input sequences
        ms1 = u'vache-s'
        ms2 = u'cheval'
        ms3 = u'vache-ait'
        ms4 = u'tombe-ait'
        params = json.dumps({'morpheme_sequences': [ms1, ms2, ms3, ms4]})
        response = self.app.put(url(controller='morphologies', action='applyup',
                    id=morphology_id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp[ms1] == ['vache%scow-s%sPL' % (h.rare_delimiter, h.rare_delimiter)]
        assert resp[ms2] == ['cheval%shorse' % h.rare_delimiter]
        assert resp[ms3] == [None]
        assert resp[ms4] == ['tombe%sfall-ait%s3SG.IMPV' % (h.rare_delimiter, h.rare_delimiter)]

    @nottest
    def test_i_large_datasets(self):
        """Tests that morphological parser functionality works with large datasets.

        .. note::

            This test only works if MySQL is being used as the RDBMS for the test
            *and* there is a file in 
            ``onlinelinguisticdatabase/onlinelinguisticdatabase/tests/data/datasets/``
            that is a MySQL dump file of a valid OLD database.  The name of this file
            can be configured by setting the ``old_dump_file`` variable.  Note that no
            such dump file is provided with the OLD source since the file used by the
            developer contains data that cannot be publicly shared.

        """

        # If foma is not installed, exit.
        if not h.foma_installed(force_check=True):
            return

        # Configuration

        # The ``old_dump_file`` variable holds the name of a MySQL dump file in /tests/data/datasets
        # that will be used to populate the database.
        old_dump_file = 'blaold.sql'
        backup_dump_file = 'old_test_dump.sql'

        # The ``precompiled_morphophonology`` variable holds the name of a compiled foma FST that
        # maps surface representations to sequences of morphemes.  A file with this name should be
        # present in /tests/data/morphophonologies or else the variable should be set to None.
        pregenerated_morphophonology = None # 'blaold_morphophonology.script'
        precompiled_morphophonology = None # 'blaold_morphophonology.foma'

        # Here we load a whole database from the mysqpl dump file specified in ``tests/data/datasets/<old_dump_file>``.
        old_dump_file_path = os.path.join(self.test_datasets_path, old_dump_file)
        backup_dump_file_path = os.path.join(self.test_datasets_path, backup_dump_file)
        tmp_script_path = os.path.join(self.test_datasets_path, 'tmp.sh')
        if not os.path.isfile(old_dump_file_path):
            return
        config = h.get_config(config_filename='test.ini')
        SQLAlchemyURL = config['sqlalchemy.url']
        if not SQLAlchemyURL.split(':')[0] == 'mysql':
            return
        rdbms, username, password, db_name = SQLAlchemyURL.split(':')
        username = username[2:]
        password = password.split('@')[0]
        db_name = db_name.split('/')[-1]
        # First dump the existing database so we can load it later.
        with open(tmp_script_path, 'w') as tmpscript:
            tmpscript.write('#!/bin/sh\nmysqldump -u %s -p%s %s > %s' % (username, password, db_name, backup_dump_file_path))
        os.chmod(tmp_script_path, 0744)
        with open(os.devnull, "w") as fnull:
            call([tmp_script_path], stdout=fnull, stderr=fnull)
        # Now load the dump file of the large database (from old_dump_file)
        with open(tmp_script_path, 'w') as tmpscript:
            tmpscript.write('#!/bin/sh\nmysql -u %s -p%s %s < %s' % (username, password, db_name, old_dump_file_path))
        with open(os.devnull, "w") as fnull:
            call([tmp_script_path], stdout=fnull, stderr=fnull)

        # Recreate the default users that the loaded dump file deleted
        administrator = h.generate_default_administrator()
        contributor = h.generate_default_contributor()
        viewer = h.generate_default_viewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        ################################################################################
        # PHONOLOGY
        ################################################################################

        # Create a Blackfoot phonology with the test phonology script
        params = self.phonology_create_params.copy()
        params.update({
            'name': u'Blackfoot Phonology',
            'description': u'The phonological rules of Frantz (1997) as FSTs',
            'script': self.blackfoot_phonology_script
        })
        params = json.dumps(params)
        response = self.app.post(url('phonologies'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        phonology_id = resp['id']

        ################################################################################
        # MORPHOLOGY
        ################################################################################

        # Create a lexicon form search and corpus
        # The code below constructs a query that finds a (large) subset of the Blackfoot morphemes.
        # Notes for future morphology creators:
        # 1. the "oth" category is a mess: detangle the nominalizer, inchoative, transitive suffixes, etc. from
        #    one another and from the numerals and temporal modifiers -- ugh!
        # 2. the "pro" category" is also a mess: clearly pronoun-forming iisto does not have the same distribution 
        #    as the verbal suffixes aiksi and aistsi!  And oht, the LING/means thing, is different again...
        # 3. hkayi, that thing at the end of demonstratives, is not agra, what is it? ...
        # 4. the dim category contains only 'sst' 'DIM' and is not used in any forms ...
        lexical_category_names = ['nan', 'nin', 'nar', 'nir', 'vai', 'vii', 'vta', 'vti', 'vrt', 'adt',
            'drt', 'prev', 'med', 'fin', 'oth', 'o', 'und', 'pro', 'asp', 'ten', 'mod', 'agra', 'agrb', 'thm', 'whq',
            'num', 'stp', 'PN']
        durative_morpheme = 15717
        hkayi_morpheme = 23429
        query = {'filter': ['and', [['Form', 'syntactic_category', 'name', 'in', lexical_category_names],
                                    ['not', ['Form', 'morpheme_break', 'regex', '[ -]']],
                                    ['not', ['Form', 'id', 'in', [durative_morpheme, hkayi_morpheme]]],
                                    ['not', ['Form', 'grammaticality', '=', '*']]
                                   ]]}
        smaller_query_for_rapid_testing = {'filter': ['and', [['Form', 'id', '<', 1000],
                                    ['Form', 'syntactic_category', 'name', 'in', lexical_category_names]]]}
        params = self.form_search_create_params.copy()
        params.update({
            'name': u'Blackfoot morphemes',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        lexicon_form_search_id = json.loads(response.body)['id']
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of Blackfoot morphemes',
            'form_search': lexicon_form_search_id
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        lexicon_corpus_id = json.loads(response.body)['id']

        # Create a rules corpus
        # The goal here is to exclude things that look like words but are not really words, i.e., 
        # morphemes; as a heuristic we search for forms categorized as 'sent' or whose transcription
        # value contains a space.
        query = {'filter': ['and', [['or', [['Form', 'syntactic_category', 'name', '=', u'sent'],
                                            ['Form', 'transcription', 'like', '% %']]],
                                   ['Form', 'grammaticality', '=', '']]]}
        #query = {'filter': ['Form', 'syntactic_category_string', '=', 'agra-vai']}
        smaller_query_for_rapid_testing = {'filter': ['and', [
                                ['or', [['Form', 'syntactic_category', 'name', '=', u'sent'],
                                        ['Form', 'transcription', 'like', '% %']]],
                                ['Form', 'id', '<', 23000],
                                ['Form', 'id', '>', 22000]]]}
        params = self.form_search_create_params.copy()
        params.update({
            'name': u'Find Blackfoot sentences',
            'description': u'Returns all sentential forms',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        rules_form_search_id = json.loads(response.body)['id']
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of Blackfoot sentences',
            'form_search': rules_form_search_id
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        rules_corpus_id = json.loads(response.body)['id']

        # Now we reduce the number of category-based word-formation rules by extracting all such
        # rules implicit in the rules corpus that have only one token.  With the Blackfoot database and the
        # rules corpus form search defined above, this removes more than 1000 sequences from the just over
        # 1,800 that are currently generated, a not insubstantial reduction in complexity of the resulting morphology FST.

        # Get the category sequence types of all of the words in the rules corpus ordered by their counts, minus
        # those with only one count..
        minimum_token_count = 5
        params = {'minimum_token_count': minimum_token_count}
        response = self.app.get(url(controller='corpora', action='get_word_category_sequences', id=rules_corpus_id),
                params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        log.debug(len(resp))
        word_category_sequences = u' '.join([word_category_sequence for word_category_sequence, ids in resp])
        word_category_sequences = u'agra-vai vai-agrb'

        # Now create a morphology using the lexicon and rules defined by word_category_sequences
        name = u'Morphology of Blackfoot'
        params = self.morphology_create_params.copy()
        params.update({
            'name': name,
            'lexicon_corpus': lexicon_corpus_id,
            'rules': word_category_sequences,
            'script_type': u'lexc',
            'extract_morphemes_from_rules_corpus': False
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin_appset)
        resp = json.loads(response.body)
        morphology_id = resp['id']
        assert resp['name'] == name
        assert resp['script_type'] == u'lexc'

        # Generate the morphology's script without compiling it.
        response = self.app.put(url(controller='morphologies', action='generate',
                    id=morphology_id), headers=self.json_headers,
                    extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        generate_attempt = resp['generate_attempt']

        # Poll ``GET /morphologies/morphology_id`` until ``generate_attempt`` has changed.
        seconds_elapsed = 0
        wait = 2
        while True:
            response = self.app.get(url('morphology', id=morphology_id),
                        headers=self.json_headers, extra_environ=self.extra_environ_contrib)
            resp = json.loads(response.body)
            if generate_attempt != resp['generate_attempt']:
                log.debug('Generate attempt for morphology %d has terminated.' % morphology_id)
                break
            else:
                log.debug('Waiting for morphology %d\'s script to generate: %s' % (
                    morphology_id, self.human_readable_seconds(seconds_elapsed)))
            sleep(wait)
            seconds_elapsed = seconds_elapsed + wait

        ################################################################################
        # MORPHOLOGICAL PARSER
        ################################################################################

        # Create a morphological parser for Blackfoot
        params = self.morphological_parser_create_params.copy()
        params.update({
            'name': u'Morphological parser for Blackfoot',
            'phonology': phonology_id,
            'morphology': morphology_id,
            'language_model': rules_corpus_id
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologicalparsers'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morphological_parser_id = resp['id']

        # Compile the morphological parser's morphophonology script if necessary, cf. precompiled_morphophonology and pregenerated_morphophonology.
        morphological_parser_directory = os.path.join(self.morphological_parsers_path, 'morphological_parser_%d' % morphological_parser_id)
        morphophonology_binary_filename = 'morphophonology_%d.foma' % morphological_parser_id
        morphophonology_script_filename = 'morphological_parser_%d.script' % morphological_parser_id
        morphophonology_binary_path = os.path.join(morphological_parser_directory, morphophonology_binary_filename )
        morphophonology_script_path = os.path.join(morphological_parser_directory, morphophonology_script_filename )
        try:
            precompiled_morphophonology_path = os.path.join(self.test_morphophonologies_path, precompiled_morphophonology)
            pregenerated_morphophonology_path = os.path.join(self.test_morphophonologies_path, pregenerated_morphophonology)
        except Exception:
            precompiled_morphophonology_path = None
            pregenerated_morphophonology_path = None
        if (precompiled_morphophonology_path and pregenerated_morphophonology_path and 
           os.path.exists(precompiled_morphophonology_path) and os.path.exists(pregenerated_morphophonology_path)):
            # Use the precompiled morphophonology script if it's available,
            copyfileobj(open(precompiled_morphophonology_path, 'rb'), open(morphophonology_binary_path, 'wb'))
            copyfileobj(open(pregenerated_morphophonology_path, 'rb'), open(morphophonology_script_path, 'wb'))
        else:
            # Generate the parser's morphophonology FST, compile it and generate the morphemic language model
            response = self.app.put(url(controller='morphologicalparsers', action='generate_and_compile',
                id=morphological_parser_id), headers=self.json_headers, extra_environ=self.extra_environ_admin)
            resp = json.loads(response.body)
            morphological_parser_compile_attempt = resp['compile_attempt']

            # Poll ``GET /morphologicalparsers/morphological_parser_id`` until ``compile_attempt`` has changed.
            seconds_elapsed = 0
            wait = 10
            while True:
                response = self.app.get(url('morphologicalparser', id=morphological_parser_id),
                            headers=self.json_headers, extra_environ=self.extra_environ_contrib)
                resp = json.loads(response.body)
                if morphological_parser_compile_attempt != resp['compile_attempt']:
                    log.debug('Compile attempt for morphological parser %d has terminated.' % morphological_parser_id)
                    break
                else:
                    log.debug('Waiting for morphological parser %d to compile (%s) ...' % (
                        morphological_parser_id, self.human_readable_seconds(seconds_elapsed)))
                sleep(wait)
                seconds_elapsed = seconds_elapsed + wait

        # Test applyup on the mophological parser's morphophonology FST
        transcription1 = u'nitsspiyi'
        transcription1_correct_parse = u'nit%s1-ihpiyi%sdance' % (h.rare_delimiter, h.rare_delimiter)
        transcription2 = u'aaniit'
        transcription2_correct_parse = u'waanii%ssay-t%sIMP' % (h.rare_delimiter, h.rare_delimiter)
        params = json.dumps({'transcriptions': [transcription1, transcription2]})
        response = self.app.put(url(controller='morphologicalparsers', action='applyup',
                    id=morphological_parser_id), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        assert transcription1_correct_parse in resp[transcription1]
        assert transcription2_correct_parse in resp[transcription2]

    @nottest
    def test_z_cleanup(self):
        """Clean up after the tests."""

        TestController.tearDown(
                self,
                clear_all_tables=True,
                del_global_app_set=True,
                dirs_to_destroy=['user', 'morphology', 'corpus', 'morphological_parser'])

