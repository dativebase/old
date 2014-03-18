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
import codecs
import simplejson as json
from time import sleep
from nose.tools import nottest
from sqlalchemy.sql import desc
from onlinelinguisticdatabase.tests import TestController, url
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
from subprocess import call
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import MorphemeLanguageModel, MorphemeLanguageModelBackup

log = logging.getLogger(__name__)

class TestMorphemelanguagemodelsController(TestController):
    """Tests the morpheme_language_models controller.  WARNING: the tests herein are pretty messy.  The higher 
    ordered tests will fail if the previous tests have not been run.

    TODO: add more tests where we try to create deficient LMs.

    """

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
    def test_a_create(self):
        """Tests that POST /morphemelanguagemodels creates a new morphology.

        """

        # Create the default application settings
        application_settings = h.generate_default_application_settings()
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

            ('Les chat nageaient.', 'le-s chat-s nage-aient', 'the-PL cat-PL swim-3PL.IMPV', 'The cats were swimming.', cats['S']),
            ('La tortue parlait', 'la tortue parle-ait', 'the turtle speak-3SG.IMPV', 'The turtle was speaking.', cats['S']),
            ('Les oiseaux parlaient', 'le-s oiseau-s parle-aient', 'the-PL bird-PL speak-3PL.IMPV', 'The birds were speaking.', cats['S']),
            ('Le fourmi grimpait', 'le fourmi grimpe-ait', 'the ant climb-3SG.IMPV', 'The ant was climbing.', cats['S']),
            ('Les grenouilles nageaient', 'le-s grenouille-s nage-aient', 'the-PL frog-PL swim-3PL.IMPV', 'The frogs were swimming.', cats['S']),
            ('Le cheval tombait', 'le cheval tombe-ait', 'the horse fall-3SG.IMPV', 'The horse was falling.', cats['S'])
        )

        for tuple_ in dataset:
            self.create_form(*map(unicode, tuple_))

        # Create the restricted tag
        restricted_tag = h.generate_restricted_tag()
        Session.add(restricted_tag)

        # Create a form search that finds sentences
        query = {'filter': ['Form', 'syntactic_category', 'name', '=', u'S']}
        params = self.form_search_create_params.copy()
        params.update({
            'name': u'Find sentences',
            'description': u'Returns all sentential forms',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        sentential_form_search_id = json.loads(response.body)['id']

        # Create a corpus of sentences
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of sentences',
            'form_search': sentential_form_search_id
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        sentential_corpus_id = json.loads(response.body)['id']

        # Create a morpheme language model using the sentential corpus.
        name = u'Morpheme language model'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'corpus': sentential_corpus_id,
            'toolkit': 'mitlm'
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'
        assert resp['order'] == 3
        assert resp['smoothing'] == u'' # The ModKN smoothing algorithm is the implicit default with MITLM
        assert resp['restricted'] == False

        # Attempt to compute the perplexity of the LM before its files have been generated.  Expect this
        # to work: perplexity generation creates its own pairs of test/training sets.
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log, wait=1, vocal=False)
        perplexity = resp['perplexity']
        log.debug('Perplexity of super toy french (6 sentence corpus, ModKN, n=3): %s' % perplexity)

        # Attempt to get the ARPA file of the LM before it exists and expect to fail.
        response = self.app.get(url(controller='morphemelanguagemodels', action='serve_arpa', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == 'The ARPA file for morpheme language model %d has not been compiled yet.' % morpheme_language_model_id

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log, wait=1, vocal=False)
        assert resp['generate_message'] == u'Language model successfully generated.'
        assert resp['restricted'] == False

        # Get the ARPA file of the LM as a viewer.
        response = self.app.get(url(controller='morphemelanguagemodels', action='serve_arpa',
            id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_view)
        assert response.content_type == u'text/plain'
        arpa = unicode(response.body, encoding='utf8')
        assert h.rare_delimiter.join([u'parle', u'speak', u'V']) in arpa

        # Restrict the first sentential form -- relevant for testing the restriction percolation into LMs.
        sentence1 = Session.query(model.Form).filter(model.Form.syntactic_category.has(
            model.SyntacticCategory.name==u'S')).all()[0]
        sentence1.tags.append(restricted_tag)
        Session.commit()

        # Again generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log, wait=1, vocal=False)
        assert resp['generate_message'] == u'Language model successfully generated.'
        assert resp['restricted'] == True # post file generation the LM should now be restricted because of the restricted Form.

        # Attempt to get the ARPA file of the LM as a viewer but expect to fail this time.
        response = self.app.get(url(controller='morphemelanguagemodels', action='serve_arpa', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_view, status=403)
        resp = json.loads(response.body)
        assert response.content_type == u'application/json'
        assert resp == h.unauthorized_msg

        # Attempt to get the ARPA file of the LM as an administrator and expect to succeed.
        response = self.app.get(url(controller='morphemelanguagemodels', action='serve_arpa',
            id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        assert response.content_type == u'text/plain'
        arpa = unicode(response.body, encoding='utf8')
        assert h.rare_delimiter.join([u'parle', u'speak', u'V']) in arpa

        # Get some probabilities
        likely_word = u'%s %s' % (
            h.rare_delimiter.join([u'chat', u'cat', u'N']),
            h.rare_delimiter.join([u's', u'PL', u'PHI']))
        unlikely_word = u'%s %s' % (
            h.rare_delimiter.join([u's', u'PL', u'PHI']),
            h.rare_delimiter.join([u'chat', u'cat', u'N']))
        ms_params = json.dumps({'morpheme_sequences': [likely_word, unlikely_word]})
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities',
            id=morpheme_language_model_id),
            ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        likely_word_log_prob = resp[likely_word]
        unlikely_word_log_prob = resp[unlikely_word]
        assert pow(10, likely_word_log_prob) > pow(10, unlikely_word_log_prob)

        # Create a morpheme language model using the same sentential corpus but with some other MITLM-specific settings.
        name = u'Morpheme language model FixKN'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'corpus': sentential_corpus_id,
            'toolkit': 'mitlm',
            'order': 4,
            'smoothing': 'FixKN'
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'
        assert resp['order'] == 4
        assert resp['smoothing'] == u'FixKN'

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log, wait=1, vocal=False)

        # Get probabilities again
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities', id=morpheme_language_model_id),
            ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_likely_word_log_prob = resp[likely_word]
        new_unlikely_word_log_prob = resp[unlikely_word]
        assert pow(10, new_likely_word_log_prob) > pow(10, new_unlikely_word_log_prob)
        assert new_likely_word_log_prob != likely_word_log_prob
        assert new_unlikely_word_log_prob != unlikely_word_log_prob

        # Compute the perplexity of the language model just created/generated.  This request will cause
        # the system to automatically split the corpus of the LM into 5 distinct, randomly generated
        # training (90%) and test (10%) sets and compute the perplexity of each test set according to 
        # the LM generated from its training set and return the average of these 5 perplexity calculations.
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log, wait=1, vocal=False)
        perplexity = resp['perplexity']
        log.debug('Perplexity of super toy french (6 sentence corpus, FixKN, n=4): %s' % perplexity)

        # Attempt to create a morpheme language model that lacks a corpus and has invalid values
        # for toolkit and order -- expect to fail.
        name = u'Morpheme language model with no corpus'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'toolkit': 'mitlm_lmlmlm',
            'order': 7,
            'smoothing': 'strawberry' # this error will only be caught if everything else is groovey
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['corpus'] == u'Please enter a value'
        assert resp['errors']['order'] == u'Please enter a number that is 5 or smaller'
        assert 'toolkit' in resp['errors']

        # Attempt to create a morpheme language model that has an invalid smoothing value and expect to fail.
        name = u'Morpheme language model with no corpus'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'toolkit': 'mitlm',
            'order': 3,
            'smoothing': 'strawberry', # error that will now be caught
            'corpus': sentential_corpus_id
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['errors'] == u'The LM toolkit mitlm implements no such smoothing algorithm strawberry.'

        # Create a category-based morpheme language model.
        name = u'Category-based mMorpheme language model'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'categorial': True,
            'name': name,
            'corpus': sentential_corpus_id,
            'toolkit': 'mitlm',
            'order': 4,
            'smoothing': 'FixKN'
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'
        assert resp['order'] == 4
        assert resp['smoothing'] == u'FixKN'
        assert resp['categorial'] == True

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log, wait=1,
                vocal=True, task_descr='generate categorial MLM')

        # Get the ARPA file of the LM.
        response = self.app.get(url(controller='morphemelanguagemodels', action='serve_arpa', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        assert response.content_type == u'text/plain'
        arpa = unicode(response.body, encoding='utf8')

        # The ARPA-formatted LM file will contain (at least) these category-based bi/trigrams:
        assert u'D PHI' in arpa
        assert u'N PHI' in arpa
        assert u'V AGR' in arpa
        assert u'<s> V AGR' in arpa

        # Get the probabilities of our likely and unlikely words based on their category
        likely_word = u'N PHI'
        unlikely_word = u'PHI N'
        ms_params = json.dumps({'morpheme_sequences': [likely_word, unlikely_word]})
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities',
            id=morpheme_language_model_id), ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        likely_word_log_prob = resp[likely_word]
        unlikely_word_log_prob = resp[unlikely_word]
        assert likely_word_log_prob > unlikely_word_log_prob

        # Compute the perplexity of the category-based language model.
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity',
            id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log, wait=1, vocal=False)
        perplexity = resp['perplexity']
        log.debug('Perplexity of super toy french (6 sentence corpus, category-based, FixKN, n=4): %s' % perplexity)

    @nottest
    def test_b_index(self):
        """Tests that GET /morpheme_language_models returns all morpheme_language_model resources."""

        morpheme_language_models = Session.query(MorphemeLanguageModel).all()

        # Get all morpheme_language_models
        response = self.app.get(url('morphemelanguagemodels'), headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp) == 3

        # Test the paginator GET params.
        paginator = {'items_per_page': 1, 'page': 1}
        response = self.app.get(url('morphemelanguagemodels'), paginator, headers=self.json_headers,
                                extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert len(resp['items']) == 1
        assert resp['items'][0]['name'] == morpheme_language_models[0].name
        assert response.content_type == 'application/json'

        # Test the order_by GET params.
        order_by_params = {'order_by_model': 'MorphemeLanguageModel', 'order_by_attribute': 'id',
                     'order_by_direction': 'desc'}
        response = self.app.get(url('morphemelanguagemodels'), order_by_params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp[0]['id'] == morpheme_language_models[-1].id
        assert response.content_type == 'application/json'

        # Test the order_by *with* paginator.
        params = {'order_by_model': 'MorphemeLanguageModel', 'order_by_attribute': 'id',
                     'order_by_direction': 'desc', 'items_per_page': 1, 'page': 3}
        response = self.app.get(url('morphemelanguagemodels'), params,
                        headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert morpheme_language_models[0].name == resp['items'][0]['name']

        # Expect a 400 error when the order_by_direction param is invalid
        order_by_params = {'order_by_model': 'MorphemeLanguageModel', 'order_by_attribute': 'name',
                     'order_by_direction': 'descending'}
        response = self.app.get(url('morphemelanguagemodels'), order_by_params, status=400,
            headers=self.json_headers, extra_environ=self.extra_environ_view)
        resp = json.loads(response.body)
        assert resp['errors']['order_by_direction'] == u"Value must be one of: asc; desc (not u'descending')"
        assert response.content_type == 'application/json'

    @nottest
    def test_d_show(self):
        """Tests that GET /morphemelanguagemodels/id returns the morpheme_language_model with id=id or an appropriate error."""

        morpheme_language_models = Session.query(MorphemeLanguageModel).all()

        # Try to get a morpheme_language_model using an invalid id
        id = 100000000000
        response = self.app.get(url('morphemelanguagemodel', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no morpheme language model with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('morphemelanguagemodel', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('morphemelanguagemodel', id=morpheme_language_models[0].id), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['name'] == morpheme_language_models[0].name
        assert resp['description'] == morpheme_language_models[0].description
        assert response.content_type == 'application/json'

    @nottest
    def test_e_new_edit(self):
        """Tests that GET /morphemelanguagemodels/new and GET /morphemelanguagemodels/id/edit return the data needed to create or update a morpheme_language_model.

        """

        morpheme_language_models = Session.query(MorphemeLanguageModel).all()
        corpora = Session.query(model.Corpus).all()
        morphologies = Session.query(model.Morphology).all()
        toolkits = h.language_model_toolkits

        # Test GET /morphemelanguagemodels/new
        response = self.app.get(url('new_morphemelanguagemodel'), headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp['corpora']) == len(corpora)
        assert len(resp['morphologies']) == len(morphologies)
        assert len(resp['toolkits'].keys()) == len(toolkits.keys())

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_morphemelanguagemodel', id=morpheme_language_models[0].id), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_morphemelanguagemodel', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no morpheme language model with id %s' % id in json.loads(response.body)['error']
        assert response.content_type == 'application/json'

        # No id
        response = self.app.get(url('edit_morphemelanguagemodel', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == 'The resource could not be found.'
        assert response.content_type == 'application/json'

        # Valid id
        response = self.app.get(url('edit_morphemelanguagemodel', id=morpheme_language_models[0].id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['morpheme_language_model']['name'] == morpheme_language_models[0].name
        assert len(resp['data']['corpora']) == len(corpora)
        assert len(resp['data']['morphologies']) == len(morphologies)
        assert len(resp['data']['toolkits'].keys()) == len(toolkits.keys())
        assert response.content_type == 'application/json'

    @nottest
    def test_f_update(self):
        """Tests that PUT /morphemelanguagemodels/id updates the morpheme_language_model with id=id."""

        morpheme_language_models = [json.loads(json.dumps(m, cls=h.JSONOLDEncoder))
            for m in Session.query(MorphemeLanguageModel).all()]
        morpheme_language_model_id = morpheme_language_models[0]['id']
        morpheme_language_model_1_name = morpheme_language_models[0]['name']
        morpheme_language_model_1_description = morpheme_language_models[0]['description']
        morpheme_language_model_1_modified = morpheme_language_models[0]['datetime_modified']
        morpheme_language_model_1_corpus_id = morpheme_language_models[0]['corpus']['id']
        morpheme_language_model_1_vocabulary_morphology_id = getattr(morpheme_language_models[0].get('vocabulary_morphology'), 'id', None)
        morpheme_language_model_count = len(morpheme_language_models)
        morpheme_language_model_1_dir = os.path.join(
            self.morpheme_language_models_path, 'morpheme_language_model_%d' % morpheme_language_model_id)
        morpheme_language_model_1_arpa_path = os.path.join(morpheme_language_model_1_dir,
                'morpheme_language_model.lm')
        morpheme_language_model_1_arpa = codecs.open(morpheme_language_model_1_arpa_path, mode='r', encoding='utf8').read()

        # Update the first morpheme language model.  This will create the first backup for this morpheme language model.
        original_backup_count = Session.query(MorphemeLanguageModelBackup).count()
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': morpheme_language_model_1_name,
            'description': u'New description',
            'corpus': morpheme_language_model_1_corpus_id,
            'vocabulary_morphology': morpheme_language_model_1_vocabulary_morphology_id,
            'toolkit': 'mitlm'
        })
        params = json.dumps(params)
        response = self.app.put(url('morphemelanguagemodel', id=morpheme_language_model_id), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        new_backup_count = Session.query(MorphemeLanguageModelBackup).count()
        datetime_modified = resp['datetime_modified']
        new_morpheme_language_model_count = Session.query(MorphemeLanguageModel).count()
        assert morpheme_language_model_count == new_morpheme_language_model_count
        assert datetime_modified != morpheme_language_model_1_modified
        assert resp['description'] == u'New description'
        assert response.content_type == 'application/json'
        assert original_backup_count + 1 == new_backup_count
        backup = Session.query(MorphemeLanguageModelBackup).filter(
            MorphemeLanguageModelBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(MorphemeLanguageModelBackup.id)).first()
        assert backup.datetime_modified.isoformat() == morpheme_language_model_1_modified
        assert backup.description == morpheme_language_model_1_description
        assert response.content_type == 'application/json'

        # Attempt an update with no new input and expect to fail
        response = self.app.put(url('morphemelanguagemodel', id=morpheme_language_model_id), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        morpheme_language_model_count = new_morpheme_language_model_count
        new_morpheme_language_model_count = Session.query(MorphemeLanguageModel).count()
        our_morpheme_language_model_datetime_modified = Session.query(MorphemeLanguageModel).get(morpheme_language_model_id).datetime_modified
        assert our_morpheme_language_model_datetime_modified.isoformat() == datetime_modified
        assert morpheme_language_model_count == new_morpheme_language_model_count
        assert resp['error'] == u'The update request failed because the submitted data were not new.'
        assert response.content_type == 'application/json'

    @nottest
    def test_g_history(self):
        """Tests that GET /morphemelanguagemodels/id/history returns the morpheme_language_model with id=id and its previous incarnations.

        The JSON object returned is of the form
        {'morpheme_language_model': morpheme_language_model, 'previous_versions': [...]}.

        """

        morpheme_language_models = Session.query(MorphemeLanguageModel).all()
        morpheme_language_model_id = morpheme_language_models[0].id
        morpheme_language_model_1_UUID = morpheme_language_models[0].UUID
        morpheme_language_model_1_backup_count = len(Session.query(MorphemeLanguageModelBackup).\
                filter(MorphemeLanguageModelBackup.UUID==morpheme_language_model_1_UUID).all())
        # Now get the history of the first morpheme_language_model (which was updated twice in ``test_update``.
        response = self.app.get(
            url(controller='morphemelanguagemodels', action='history', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'morpheme_language_model' in resp
        assert 'previous_versions' in resp
        assert len(resp['previous_versions']) == morpheme_language_model_1_backup_count

        # Get the same history as above, except use the UUID
        response = self.app.get(
            url(controller='morphemelanguagemodels', action='history', id=morpheme_language_model_1_UUID),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert 'morpheme_language_model' in resp
        assert 'previous_versions' in resp
        assert len(resp['previous_versions']) == morpheme_language_model_1_backup_count

        # Attempt to get the history with an invalid id and expect to fail
        response = self.app.get(
            url(controller='morphemelanguagemodels', action='history', id=123456789),
            headers=self.json_headers, extra_environ=self.extra_environ_view_appset, status=404)
        resp = json.loads(response.body)
        assert response.content_type == 'application/json'
        assert resp['error'] == u'No morpheme language models or morpheme language model backups match 123456789'

        # Further tests could be done ... cf. the tests on the history action of the phonologies controller ...

    @nottest
    def test_i_large_datasets(self):
        """Tests that morpheme language model functionality works with large datasets.

        .. note::

            This test only works if MySQL is being used as the RDBMS for the test
            *and* there is a file in 
            ``onlinelinguisticdatabase/onlinelinguisticdatabase/tests/data/datasets/``
            that is a MySQL dump file of a valid OLD database.  The name of this file
            can be configured by setting the ``old_dump_file`` variable.  Note that no
            such dump file is provided with the OLD source since the file used by the
            developer contains data that cannot be publicly shared.

        """
        # Configuration

        # The ``old_dump_file`` variable holds the name of a MySQL dump file in /tests/data/datasets
        # that will be used to populate the database.
        old_dump_file = 'blaold.sql'
        backup_dump_file = 'old_test_dump.sql'

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
        # Note: the --single-transaction option seems to be required (on Mac MySQL 5.6 using InnoDB tables ...)
        # see http://forums.mysql.com/read.php?10,108835,112951#msg-112951
        with open(tmp_script_path, 'w') as tmpscript:
            tmpscript.write('#!/bin/sh\nmysqldump -u %s -p%s --single-transaction --no-create-info --result-file=%s %s' % (
                username, password, backup_dump_file_path, db_name))
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
        # CORPUS
        ################################################################################

        # Create a corpus of forms containing words -- to be used to estimate ngram probabilities
        # The goal here is to exclude things that look like words but are not really words, i.e., 
        # morphemes; as a heuristic we search for grammatical forms categorized as 'sent' or whose
        # transcription value contains a space or a hyphen-minus.
        query = {'filter': ['and', [['or', [['Form', 'syntactic_category', 'name', '=', u'sent'],
                                            ['Form', 'morpheme_break', 'like', '% %'],
                                            ['Form', 'morpheme_break', 'like', '%-%']]],
                                   ['Form', 'syntactic_category_string', '!=', None],
                                   ['Form', 'grammaticality', '=', '']]]}
        params = self.form_search_create_params.copy()
        params.update({
            'name': u'Forms containing words',
            'search': query
        })
        params = json.dumps(params)
        response = self.app.post(url('formsearches'), params, self.json_headers, self.extra_environ_admin)
        words_form_search_id = json.loads(response.body)['id']

        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of forms that contain words',
            'form_search': words_form_search_id
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        words_corpus_id = json.loads(response.body)['id']

        ################################################################################
        # LM 1 -- trigram, ModKN
        ################################################################################

        # Now create a morpheme language model using the corpus of forms containing words
        # Note that the default smoothing algorithm will be ModKN and the order will be 3
        name = u'Morpheme language model for Blackfoot'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'corpus': words_corpus_id,
            'toolkit': u'mitlm'
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin_appset)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log)
        assert resp['generate_message'] == u'Language model successfully generated.'

        # Get some probabilities: nit-ihpiyi should be more probable than ihpiyi-nit
        likely_word = u'%s %s' % (
            h.rare_delimiter.join([u'nit', u'1', u'agra']),
            h.rare_delimiter.join([u'ihpiyi', u'dance', u'vai']))
        unlikely_word = u'%s %s' % (
            h.rare_delimiter.join([u'ihpiyi', u'dance', u'vai']),
            h.rare_delimiter.join([u'nit', u'1', u'agra']))
        ms_params = json.dumps({'morpheme_sequences': [likely_word, unlikely_word]})
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities', id=morpheme_language_model_id),
            ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        likely_word_log_prob = resp[likely_word]
        unlikely_word_log_prob = resp[unlikely_word]
        assert pow(10, likely_word_log_prob) > pow(10, unlikely_word_log_prob)

        # Compute the perplexity of the LM 
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log)
        perplexity = resp['perplexity']

        # count how many words constitute the corpus.
        lm_corpus_path = os.path.join(self.morpheme_language_models_path,
                'morpheme_language_model_%s' % morpheme_language_model_id,
                'morpheme_language_model.txt')
        word_count = 0
        with codecs.open(lm_corpus_path, encoding='utf8') as f:
            for line in f:
                word_count += 1
        log.debug('Perplexity of Blackfoot LM %s (%s sentence corpus, ModKN, n=3): %s' % (
            morpheme_language_model_id, word_count, perplexity))

        ################################################################################
        # LM 2 -- trigram, ModKN, category-based
        ################################################################################

        # Recreate the above-created LM except make it category-based.
        name = u'Category-based morpheme language model for Blackfoot'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'categorial': True,
            'name': name,
            'corpus': words_corpus_id,
            'toolkit': u'mitlm'
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin_appset)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log)
        assert resp['generate_message'] == u'Language model successfully generated.'

        # Get some probabilities: agra-vai should be more probable than vai-agra
        likely_category_word = u'agra vai'
        unlikely_category_word = u'vai agra'
        ms_params = json.dumps({'morpheme_sequences': [likely_category_word, unlikely_category_word]})
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities', id=morpheme_language_model_id),
            ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        likely_category_word_log_prob = resp[likely_category_word]
        unlikely_category_word_log_prob = resp[unlikely_category_word]
        assert pow(10, likely_category_word_log_prob) > pow(10, unlikely_category_word_log_prob)

        # Compute the perplexity of the LM 
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log)
        category_based_perplexity = resp['perplexity']

        # count how many words constitute the corpus.
        lm_corpus_path = os.path.join(self.morpheme_language_models_path, 'morpheme_language_model_%s' % morpheme_language_model_id,
                'morpheme_language_model.txt')
        word_count = 0
        with codecs.open(lm_corpus_path, encoding='utf8') as f:
            for line in f:
                word_count += 1
        log.debug('Perplexity of Blackfoot category-based LM %s (%s sentence corpus, ModKN, n=3): %s' % (
            morpheme_language_model_id, word_count, category_based_perplexity))

        ################################################################################
        # MORPHOLOGY -- we'll use it to specify a fixed vocabulary for subsequent LMs.
        ################################################################################

        # Create a form search that finds lexical items (i.e., Blackfoot morphemes) and make a corpus out of it.
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

        # Create a form search of forms containing blackfoot words and use it to create a corpus of
        # word-containing forms.  The goal here is to find forms that are explicitly sentences or that
        # contain spaces or morpheme delimiters in their morpheme break fields.
        query = {'filter': ['and', [['or', [['Form', 'syntactic_category', 'name', '=', u'sent'],
                                            ['Form', 'morpheme_break', 'like', '%-%'],
                                            ['Form', 'morpheme_break', 'like', '% %']]],
                                   ['Form', 'grammaticality', '=', '']]]}
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
        # rules implicit in the rules corpus that have four or fewer execmplars.  With the Blackfoot database and the
        # rules corpus form search defined above, this removes more than 1000 sequences from the just over
        # 1,800 that are currently generated, a not insubstantial reduction in complexity of the resulting morphology FST.

        # Get the category sequence types of all of the words in the rules corpus ordered by their counts, minus
        # those with fewer than 5 counts.
        minimum_token_count = 5
        params = {'minimum_token_count': minimum_token_count}
        response = self.app.get(url(controller='corpora', action='get_word_category_sequences', id=rules_corpus_id),
                params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        word_category_sequences = u' '.join([word_category_sequence for word_category_sequence, ids in resp])

        # Now create a morphology using the lexicon and rules defined by word_category_sequences
        morphology_name = u'Morphology of Blackfoot'
        params = self.morphology_create_params.copy()
        params.update({
            'name': morphology_name,
            'lexicon_corpus': lexicon_corpus_id,
            'rules': word_category_sequences,
            'script_type': u'lexc',
            'extract_morphemes_from_rules_corpus': False # This is irrelevant since this morphology doesn't use a rules corpus
        })
        params = json.dumps(params)
        response = self.app.post(url('morphologies'), params, self.json_headers, self.extra_environ_admin_appset)
        resp = json.loads(response.body)
        morphology_id = resp['id']
        assert resp['name'] == morphology_name
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

        # Now our morphology has a lexicon associated to it that we can use to create a vocabulary
        # for our language model.  Since the morphology will only recognize sequences of morphemes
        # that are generable using this vocabulary, we can create a language model over this fixed
        # vocabulary.

        ################################################################################
        # LM 3 -- trigram, ModKN, fixed vocab
        ################################################################################

        # Create the morpheme language model with a vocabulary_morphology value
        name = u'Morpheme language model for Blackfoot with fixed vocabulary'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'corpus': words_corpus_id,
            'toolkit': u'mitlm',
            'vocabulary_morphology': morphology_id
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin_appset)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'
        assert resp['vocabulary_morphology']['name'] == morphology_name

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log)

        # Get some probabilities: nit-ihpiyi should be more probable than ihpiyi-nit
        ms_params = json.dumps({'morpheme_sequences': [likely_word, unlikely_word]})
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities', id=morpheme_language_model_id),
            ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_likely_word_log_prob = resp[likely_word]
        new_unlikely_word_log_prob = resp[unlikely_word]
        assert pow(10, new_likely_word_log_prob) > pow(10, new_unlikely_word_log_prob)
        assert new_unlikely_word_log_prob != unlikely_word_log_prob
        assert new_likely_word_log_prob != likely_word_log_prob

        # Compute the perplexity of the LM 
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log,
            task_descr='GET PERPLEXITY OF LM %s' % morpheme_language_model_id)
        new_perplexity = resp['perplexity']

        log.debug('new_perplexity')
        log.debug(new_perplexity)
        log.debug('perplexity')
        log.debug(perplexity)
        assert new_perplexity < perplexity
        log.debug('Perplexity of Blackfoot LM %s (%s sentence corpus, ModKN, n=3, fixed vocabulary): %s' % (
            morpheme_language_model_id, word_count, new_perplexity))

        ################################################################################
        # LM 4 -- trigram, ModKN, fixed vocab, categorial
        ################################################################################

        # Create a fixed vocabulary LM that is category-based.
        name = u'Categorial morpheme language model for Blackfoot with fixed vocabulary'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'corpus': words_corpus_id,
            'toolkit': u'mitlm',
            'vocabulary_morphology': morphology_id,
            'categorial': True
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin_appset)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'
        assert resp['vocabulary_morphology']['name'] == morphology_name

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log)

        # Get some probabilities: agra-vai should be more probable than vai-agra
        ms_params = json.dumps({'morpheme_sequences': [likely_category_word, unlikely_category_word]})
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities', id=morpheme_language_model_id),
            ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        new_likely_category_word_log_prob = resp[likely_category_word]
        new_unlikely_category_word_log_prob = resp[unlikely_category_word]
        assert pow(10, new_likely_category_word_log_prob) > pow(10, new_unlikely_category_word_log_prob)
        assert new_unlikely_category_word_log_prob != unlikely_category_word_log_prob
        assert new_likely_category_word_log_prob != likely_category_word_log_prob

        # Compute the perplexity of the LM 
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity',
            id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log,
            task_descr='GET PERPLEXITY OF LM %s' % morpheme_language_model_id)
        new_category_based_perplexity = resp['perplexity']

        log.debug('Perplexity of Blackfoot LM %s (%s sentence corpus, ModKN, n=3, '
            'fixed vocabulary, category-based): %s' % (
            morpheme_language_model_id, word_count, new_category_based_perplexity))
        # The perplexity of this categorial LM should (and is usually, but not always) lower
        # than the previous categorial one that did not have a fixed vocab.  As a result, the
        # assertion below cannot be categorically relied upon.
        #assert new_category_based_perplexity < (1 + category_based_perplexity)

        ################################################################################
        # LM 5 -- trigram, ModKN, fixed vocab, corpus weighted towards 'nit-ihpiyi'
        ################################################################################

        # Create a language model built on a corpus that contains multiple tokens of certain
        # forms.  This allows us to tinker with the probabilities.  In this specific case,
        # I stack the corpus with forms containing 'nit|1-ihpiyi|dance'.

        # First get the ids of the forms in the corpus
        query = json.dumps({'query': {'filter': ['Form', 'corpora', 'id', '=', words_corpus_id]}})
        response = self.app.post(url('/forms/search'), query, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        form_ids = [f['id'] for f in resp]

        # Now get the ids of all forms in the corpus that have nit-ihpiyi 1-dance in them and add them 100 times to the form ids list
        nit_ihpiyi_ids = [f['id'] for f in resp if 'nit|1|agra-ihpiyi|dance|vai' in f['break_gloss_category']]
        form_ids += nit_ihpiyi_ids * 100

        # Create a new corpus that is defined by a list of ids corresponding to forms which contain an inordinate amount of nit-ihpiyi words.
        params = self.corpus_create_params.copy()
        params.update({
            'name': u'Corpus of forms that contain words with lots of nit-ihpiyi words',
            'content': u','.join(map(str, form_ids))
        })
        params = json.dumps(params)
        response = self.app.post(url('corpora'), params, self.json_headers, self.extra_environ_admin)
        nit_ihpiyi_words_corpus_id = json.loads(response.body)['id']

        # Create the morpheme language model with a vocabulary_morphology value
        name = u'Morpheme language model for Blackfoot with fixed vocabulary and weighted towards nit-ihpiyi words'
        params = self.morpheme_language_model_create_params.copy()
        params.update({
            'name': name,
            'corpus': nit_ihpiyi_words_corpus_id,
            'toolkit': u'mitlm',
            'vocabulary_morphology': morphology_id
        })
        params = json.dumps(params)
        response = self.app.post(url('morphemelanguagemodels'), params, self.json_headers, self.extra_environ_admin_appset)
        resp = json.loads(response.body)
        morpheme_language_model_id = resp['id']
        assert resp['name'] == name
        assert resp['toolkit'] == u'mitlm'
        assert resp['vocabulary_morphology']['name'] == morphology_name

        # Generate the files of the language model
        response = self.app.put(url(controller='morphemelanguagemodels', action='generate', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_generate_attempt = resp['generate_attempt']

        # Poll GET /morphemelanguagemodels/id until generate_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'generate_attempt', lm_generate_attempt, log, 
            task_descr='GET PERPLEXITY OF L %s' % morpheme_language_model_id)

        # Get some probabilities: nit-ihpiyi should be more probable than ihpiyi-nit.
        # Also, because of the new weighted corpus, nit-ihpiyi should now be assigned a higher probability
        # than it was before.
        ms_params = json.dumps({'morpheme_sequences': [likely_word, unlikely_word]})
        response = self.app.put(url(controller='morphemelanguagemodels', action='get_probabilities', id=morpheme_language_model_id),
            ms_params, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newer_likely_word_log_prob = resp[likely_word]
        newer_unlikely_word_log_prob = resp[unlikely_word]
        assert pow(10, new_likely_word_log_prob) > pow(10, new_unlikely_word_log_prob)
        assert newer_unlikely_word_log_prob != unlikely_word_log_prob
        # Because we've given more weight to nit-ihpiyi in the LM's corpus, this word should be
        # more probable according to this LM than according to the previous one.
        assert newer_likely_word_log_prob > new_likely_word_log_prob

        # Compute the perplexity of the LM 
        response = self.app.put(url(controller='morphemelanguagemodels', action='compute_perplexity', id=morpheme_language_model_id),
            {}, self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        lm_perplexity_attempt = resp['perplexity_attempt']

        # Poll GET /morphemelanguagemodels/id until perplexity_attempt changes.
        requester = lambda: self.app.get(url('morphemelanguagemodel', id=morpheme_language_model_id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = self.poll(requester, 'perplexity_attempt', lm_perplexity_attempt, log,
            task_descr='GET PERPLEXITY OF LM %s' % morpheme_language_model_id)
        newest_perplexity = resp['perplexity']
        assert newest_perplexity < perplexity
        log.debug('Perplexity of Blackfoot LM %s (%s sentence corpus, ModKN, n=3, fixed vocabulary, corpus weighted towards nit-ihpiyi): %s' %
                (morpheme_language_model_id, word_count, newest_perplexity))

        """
        # Finally, load the original database back in so that subsequent tests can work.
        with open(tmp_script_path, 'w') as tmpscript:
            tmpscript.write('#!/bin/sh\nmysql -u %s -p%s %s < %s' % (username, password, db_name, backup_dump_file_path))
        with open(os.devnull, "w") as fnull:
            call([tmp_script_path], stdout=fnull, stderr=fnull)
        os.remove(tmp_script_path)
        os.remove(backup_dump_file_path)
        """

        sleep(1) # If I don't sleep here I get an odd thread-related error (conditional upon
        # this being the last test to be run, I think)...

    @nottest
    def test_z_cleanup(self):
        """Clean up after the tests."""

        TestController.tearDown(
                self,
                clear_all_tables=True,
                del_global_app_set=True,
                dirs_to_destroy=['user', 'morpheme_language_model', 'corpus', 'morphological_parser'])


