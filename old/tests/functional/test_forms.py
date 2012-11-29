import datetime
import logging
import simplejson as json
from nose.tools import nottest

from sqlalchemy.sql import desc
from uuid import uuid4

from old.tests import *
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h

log = logging.getLogger(__name__)


class TestFormsController(TestController):

    createParams = {
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
        'dateElicited': u''     # mm/dd/yyyy
    }

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Set up some stuff for the tests
    def setUp(self):
        pass

    # Clear all models in the database except Language; recreate the users.
    def tearDown(self):
        h.clearAllModels()
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer])
        Session.commit()

        # Perform a vacuous GET just to delete app_globals.applicationSettings
        # to clean up for subsequent tests.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        response = self.app.get(url('forms'), extra_environ=extra_environ)


    #@nottest
    def test_index(self):
        """Tests that GET /forms returns a JSON array of forms with expected values."""

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

        # Finally, issue two POST requests to create two default forms with the
        # *default* contributor as the enterer.  One form will be restricted and
        # the other will not be.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}

        # Create the restricted form.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test restricted tag transcription',
            'glosses': [{'gloss': u'test restricted tag gloss',
                         'glossGrammaticality': u''}],
            'tags': [h.getTags()[0].id]    # the restricted tag should be the only one
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restrictedFormId = resp['id']

        # Create the unrestricted form.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test restricted tag transcription 2',
            'glosses': [{'gloss': u'test restricted tag gloss 2',
                         'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        unrestrictedFormId = resp['id']

        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted myContributor should all be able to view both forms.
        # The viewer will only receive the unrestricted form.

        # An administrator should be able to view both forms.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2
        assert resp[0]['transcription'] == u'test restricted tag transcription'
        assert resp[0]['morphemeBreakIDs'] == [[[]]]
        assert resp[0]['morphemeGlossIDs'] == [[[]]]
        assert resp[0]['glosses'][0]['gloss'] == u'test restricted tag gloss'
        assert type(resp[0]['glosses'][0]['id']) == type(1)
        assert type(resp[0]['id']) == type(1)
        assert response.content_type == 'application/json'

        # The default contributor (qua enterer) should also be able to view both
        # forms.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Mycontributor (an unrestricted user) should also be able to view both
        # forms.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # A (not unrestricted) viewer should be able to view only one form.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove Mycontributor from the unrestricted users list and access to
        # the second form will be denied.
        applicationSettings = h.getApplicationSettings()
        applicationSettings.unrestrictedUsers = []
        Session.add(applicationSettings)
        Session.commit()

        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view the restricted form.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True,
                         'test.retainApplicationSettings': True}
        response = self.app.get(url('forms'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 1

        # Remove the restricted tag from the form and the viewer should now be
        # able to view it too.
        restrictedForm = Session.query(model.Form).get(restrictedFormId)
        restrictedForm.tags = []
        Session.add(restrictedForm)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 2

        # Clear all Forms (actually, everything but the tags, users and languages)
        h.clearAllModels(['User', 'Tag', 'Language'])

        # Now add 100 forms.  The even ones will be restricted, the odd ones not.
        def createFormFromIndex(index):
            form = model.Form()
            form.transcription = u'transcription %d' % index
            return form
        forms = [createFormFromIndex(i) for i in range(1, 101)]
        Session.add_all(forms)
        Session.commit()
        forms = h.getForms()
        restrictedTag = h.getRestrictedTag()
        for form in forms:
            if int(form.transcription.split(' ')[1]) % 2 == 0:
                form.tags.append(restrictedTag)
            Session.add(form)
        Session.commit()

        # An administrator should be able to retrieve all of the forms.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp) == 100
        assert resp[0]['transcription'] == u'transcription 1'

        # Test the paginator GET params.
        paginator = {'itemsPerPage': 23, 'page': 3}
        response = self.app.get(url('forms'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == 23
        assert resp['items'][0]['transcription'] == u'transcription 47'

        # The default viewer should only be able to see the odd numbered forms,
        # even with a paginator.
        itemsPerPage = 7
        page = 7
        paginator = {'itemsPerPage': itemsPerPage, 'page': page}
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('forms'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['items']) == itemsPerPage
        assert resp['items'][0]['transcription'] == u'transcription %d' % (
            ((itemsPerPage * (page - 1)) * 2) + 1)

        # Expect a 400 error when the paginator GET params are, empty, not
        # or integers that are less than 1
        paginator = {'itemsPerPage': u'a', 'page': u''}
        response = self.app.get(url('forms'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter an integer value'
        assert resp['errors']['page'] == u'Please enter a value'

        paginator = {'itemsPerPage': 0, 'page': -1}
        response = self.app.get(url('forms'), paginator, headers=self.json_headers,
                                extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['itemsPerPage'] == u'Please enter a number that is 1 or greater'
        assert resp['errors']['page'] == u'Please enter a number that is 1 or greater'

    #@nottest
    def test_create(self):
        """Tests that POST /forms correctly creates a new form."""

        # Pass some mal-formed JSON to test that a 400 error is returned.
        params = '"a'   # Bad JSON
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == u'JSON decode error: the parameters provided were not valid JSON.'

        # Create a test form.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test_create_transcription',
            'glosses': [{'gloss': u'test_create_gloss', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert type(resp) == type({})
        assert resp['transcription'] == u'test_create_transcription'
        assert resp['glosses'][0]['gloss'] == u'test_create_gloss'
        assert resp['morphemeBreakIDs'] == [[[]]]
        assert resp['enterer']['firstName'] == u'Admin'
        assert formCount == 1
        

        # Add an empty application settings and two syntactic categories.
        N = h.generateNSyntacticCategory()
        Num = h.generateNumSyntacticCategory()
        S = h.generateSSyntacticCategory()
        applicationSettings = model.ApplicationSettings()
        Session.add_all([S, N, Num, applicationSettings])
        Session.commit()

        # Create two lexical forms.
        params = self.createParams.copy()
        params.update({
            'transcription': u'chien',
            'morphemeBreak': u'chien',
            'morphemeGloss': u'dog',
            'glosses': [{'gloss': u'dog', 'glossGrammaticality': u''}],
            'syntacticCategory': Session.query(
                model.SyntacticCategory).filter(
                model.SyntacticCategory.name==u'N').first().id
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        params = self.createParams.copy()
        params.update({
            'transcription': u's',
            'morphemeBreak': u's',
            'morphemeGloss': u'PL',
            'glosses': [{'gloss': u'plural', 'glossGrammaticality': u''}],
            'syntacticCategory': Session.query(
                model.SyntacticCategory).filter(
                model.SyntacticCategory.name==u'Num').first().id
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        formCount = Session.query(model.Form).count()
        assert formCount == 3

        # Create another form whose morphemic analysis will reference the
        # lexical items created above.  Here we expect the morphemeBreakIDs,
        # morphemeGlossIDs and syntacticCategoryString to be vacuous because
        # no morpheme delimiters are specified in the application settings.
        params = self.createParams.copy()
        params.update({
            'transcription': u'Les chiens aboient.',
            'morphemeBreak': u'les chien-s aboient',
            'morphemeGloss': u'the dog-PL bark',
            'glosses': [{'gloss': u'The dogs are barking.', 'glossGrammaticality': u''}],
            'syntacticCategory': Session.query(
                model.SyntacticCategory).filter(
                model.SyntacticCategory.name==u'S').first().id
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert type(resp) == type({})
        assert resp['transcription'] == u'Les chiens aboient.'
        assert resp['glosses'][0]['gloss'] == u'The dogs are barking.'
        assert resp['syntacticCategory']['name'] == u'S'
        assert resp['morphemeBreakIDs'] == [[[]]]
        assert resp['syntacticCategoryString'] == u''
        assert resp['syntacticCategory']['name'] == u'S'
        assert formCount == 4

        # Re-create the form from above but this time add a non-empty
        # application settings.  Now we should expect the morphemeBreakIDs,
        # morphemeGlossIDs and syntacticCategoryString to have non-vacuous
        # values since '-' is specified as a morpheme delimiter.
        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add(applicationSettings)
        Session.commit()
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert resp['morphemeBreakIDs'] != [[[]]]
        assert resp['syntacticCategoryString'] != u''
        # The syntactic category string should contain 'N-Num' for 'chien-s'.
        assert u'N-Num' in resp['syntacticCategoryString']
        # The syntactic category (third value) of the first lexical match of the
        # first morpheme of the second word should be N (since 'chien' is a noun).
        assert resp['morphemeBreakIDs'][1][0][0][2] == u'N'
        assert formCount == 5

        # Recreate the above form but put morpheme delimiters in unexpected
        # places.
        params = self.createParams.copy()
        params.update({
            'transcription': u'Les chiens aboient.',
            'morphemeBreak': u'les chien- -s aboient',
            'morphemeGloss': u'the dog- -PL bark',
            'glosses': [{'gloss': u'The dogs are barking.', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        morphemeBreakIDs = resp['morphemeBreakIDs']
        assert len(morphemeBreakIDs) == 4   # 3 spaces in the mb field
        assert len(morphemeBreakIDs[1]) == 2 # 'chien-' is split into 'chien' and ''
        assert 'N-?' in resp['syntacticCategoryString'] and \
            '?-Num' in resp['syntacticCategoryString']

    #@nottest
    def test_create_invalid(self):
        """Tests that POST /forms with invalid input returns an appropriate error."""

        # Empty transcription and glosses should raise error
        formCount = Session.query(model.Form).count()
        params = self.createParams.copy()
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        newFormCount = Session.query(model.Form).count()
        assert resp['errors']['transcription'] == u'Please enter a value'
        assert resp['errors']['glosses'] == u'Please enter a value'
        assert newFormCount == formCount

        # Exceeding length restrictions should return errors also.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test create invalid transcription' * 100,
            'grammaticality': u'*',
            'phoneticTranscription': u'test create invalid phonetic transcription' * 100,
            'narrowPhoneticTranscription': u'test create invalid narrow phonetic transcription' * 100,
            'morphemeBreak': u'test create invalid morpheme break' * 100,
            'morphemeGloss': u'test create invalid morpheme gloss' * 100,
            'glosses': [{'gloss': 'test create invalid gloss', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        newFormCount = Session.query(model.Form).count()
        tooLongError = u'Enter a value not more than 255 characters long'
        assert resp['errors']['transcription'] == tooLongError
        assert resp['errors']['phoneticTranscription'] == tooLongError
        assert resp['errors']['narrowPhoneticTranscription'] == tooLongError
        assert resp['errors']['morphemeBreak'] == tooLongError
        assert resp['errors']['morphemeGloss'] == tooLongError
        assert newFormCount == formCount

        # Add some default application settings and set
        # app_globals.applicationSettings.
        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add(applicationSettings)
        Session.commit()
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        badGrammaticality = u'***'
        availableGrammaticalities = u', '.join(
            [u''] + applicationSettings.grammaticalities.split(','))
        goodGrammaticality = applicationSettings.grammaticalities.split(',')[0]

        # Create a form with an invalid grammaticality
        params = self.createParams.copy()
        params.update({
            'transcription': u'test create invalid transcription',
            'grammaticality': badGrammaticality,
            'glosses': [{'gloss': 'test create invalid gloss',
                         'glossGrammaticality': badGrammaticality}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        newFormCount = Session.query(model.Form).count()
        assert resp['errors']['grammaticality'] == \
            u'The grammaticality submitted does not match any of the available options.'
        assert resp['errors']['glosses'] == \
            u'At least one submitted gloss grammaticality does not match any of the available options.'
        assert newFormCount == formCount

        # Create a form with a valid grammaticality
        params = self.createParams.copy()
        params.update({
            'transcription': u'test create invalid transcription',
            'grammaticality': goodGrammaticality,
            'glosses': [{'gloss': 'test create invalid gloss',
                         'glossGrammaticality': goodGrammaticality}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ=extra_environ)
        resp = json.loads(response.body)
        newFormCount = Session.query(model.Form).count()
        assert resp['grammaticality'] == goodGrammaticality
        assert goodGrammaticality in [g['glossGrammaticality'] for g in
                                      resp['glosses']]
        assert newFormCount == formCount + 1

        # Create a form with some invalid many-to-one data, i.e., elicitation
        # method, speaker, enterer, etc.
        badId = 109
        badInt = u'abc'
        params = self.createParams.copy()
        params.update({
            'transcription': u'test create invalid transcription',
            'glosses': [{'gloss': 'test create invalid gloss',
                         'glossGrammaticality': u''}],
            'elicitationMethod': badId,
            'syntacticCategory': badInt,
            'speaker': badId,
            'elicitor': badInt,
            'verifier': badId,
            'source': badInt
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ=extra_environ, status=400)
        resp = json.loads(response.body)
        formCount = newFormCount
        newFormCount = Session.query(model.Form).count()
        assert resp['errors']['elicitationMethod'] == \
            u'There is no elicitation method with id %d.' % badId
        assert resp['errors']['speaker'] == \
            u'There is no speaker with id %d.' % badId
        assert resp['errors']['verifier'] == \
            u'There is no user with id %d.' % badId
        assert resp['errors']['syntacticCategory'] == u'Please enter an integer value'
        assert resp['errors']['elicitor'] == u'Please enter an integer value'
        assert resp['errors']['source'] == u'Please enter an integer value'
        assert newFormCount == formCount

        # Now create a form with some *valid* many-to-one data, i.e.,
        # elicitation method, speaker, elicitor, etc.
        elicitationMethod = h.generateDefaultElicitationMethod()
        S = h.generateSSyntacticCategory()
        speaker = h.generateDefaultSpeaker()
        source = h.generateDefaultSource()
        Session.add_all([elicitationMethod, S, speaker, source])
        Session.commit()
        contributor = Session.query(model.User).filter(
            model.User.role==u'contributor').first()
        administrator = Session.query(model.User).filter(
            model.User.role==u'administrator').first()
        params = self.createParams.copy()
        params.update({
            'transcription': u'test create invalid transcription',
            'glosses': [{'gloss': 'test create invalid gloss',
                         'glossGrammaticality': u''}],
            'elicitationMethod': h.getElicitationMethods()[0].id,
            'syntacticCategory': h.getSyntacticCategories()[0].id,
            'speaker': h.getSpeakers()[0].id,
            'elicitor': contributor.id,
            'verifier': administrator.id,
            'source': h.getSources()[0].id
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ=extra_environ)
        resp = json.loads(response.body)
        newFormCount = Session.query(model.Form).count()
        assert resp['elicitationMethod']['name'] == elicitationMethod.name
        assert resp['source']['year'] == source.year    # etc. ...
        assert newFormCount == formCount + 1

    #@nottest
    def test_create_with_inventory_validation(self):
        """Tests that POST /forms correctly applies inventory-based validation on form creation attempts."""

        # Configure the application settings with some VERY STRICT inventory-
        # based validation settings.
        orthography = model.Orthography()
        orthography.name = u'Test Orthography'
        orthography.orthography = u'o,O'
        orthography.lowercase = True
        orthography.initialGlottalStops = True
        Session.add(orthography)
        Session.commit()
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.orthographicValidation = u'Error'
        applicationSettings.narrowPhoneticInventory = u'n,p,N,P'
        applicationSettings.narrowPhoneticValidation = u'Error'
        applicationSettings.broadPhoneticInventory = u'b,p,B,P'
        applicationSettings.broadPhoneticValidation = u'Error'
        applicationSettings.morphemeBreakIsOrthographic = False
        applicationSettings.morphemeBreakValidation = u'Error'
        applicationSettings.phonemicInventory = u'p,i,P,I'
        applicationSettings.storageOrthography = h.getOrthographies()[0]
        Session.add(applicationSettings)
        Session.commit()

        # Here we indirectly cause app_globals.applicationSettings to be set to
        # an ApplicationSettings instance.  See lib.base.BaseController().__before__/__after__.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True

        # Create a form with all invalid transcriptions.
        params = self.createParams.copy()
        params.update({
            'narrowPhoneticTranscription': u'test narrow phonetic transcription validation',
            'phoneticTranscription': u'test broad phonetic transcription validation',
            'transcription': u'test orthographic transcription validation',
            'morphemeBreak': u'test morpheme break validation',
            'glosses': [{'gloss': u'test validation gloss', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ, status=400)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert u'The orthographic transcription you have entered is not valid' \
            in resp['errors']['transcription']
        assert u'The broad phonetic transcription you have entered is not valid' \
            in resp['errors']['phoneticTranscription']
        assert u'The narrow phonetic transcription you have entered is not valid' \
            in resp['errors']['narrowPhoneticTranscription']
        assert u'The morpheme segmentation you have entered is not valid' \
            in resp['errors']['morphemeBreak']
        assert u'phonemic inventory' in resp['errors']['morphemeBreak']
        assert formCount == 0

        # Create a form with some invalid and some valid transcriptions.
        params = self.createParams.copy()
        params.update({
            'narrowPhoneticTranscription': u'np NP n P N p',    # Now it's valid
            'phoneticTranscription': u'test broad phonetic transcription validation',
            'transcription': u'',
            'morphemeBreak': u'test morpheme break validation',
            'glosses': [{'gloss': u'test validation gloss', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ, status=400)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert resp['errors']['transcription'] == u'Please enter a value'
        assert u'The broad phonetic transcription you have entered is not valid' \
            in resp['errors']['phoneticTranscription']
        assert 'narrowPhoneticTranscription' not in resp
        assert u'The morpheme segmentation you have entered is not valid' \
            in resp['errors']['morphemeBreak']
        assert formCount == 0

        # Now change the validation settings to make some transcriptions valid.
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.orthographicValidation = u'Warning'
        applicationSettings.narrowPhoneticInventory = u'n,p,N,P'
        applicationSettings.narrowPhoneticValidation = u'Error'
        applicationSettings.broadPhoneticInventory = u'b,p,B,P'
        applicationSettings.broadPhoneticValidation = u'None'
        applicationSettings.morphemeBreakIsOrthographic = True
        applicationSettings.morphemeBreakValidation = u'Error'
        applicationSettings.phonemicInventory = u'p,i,P,I'
        applicationSettings.storageOrthography = h.getOrthographies()[0]
        Session.add(applicationSettings)
        Session.commit()
        params = self.createParams.copy()
        params.update({
            'narrowPhoneticTranscription': u'test narrow phonetic transcription validation',
            'phoneticTranscription': u'test broad phonetic transcription validation',
            'transcription': u'test orthographic transcription validation',
            'morphemeBreak': u'test morpheme break validation',
            'glosses': [{'gloss': u'test validation gloss', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ, status=400)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert u'transcription' not in resp['errors']
        assert u'phoneticTranscription' not in resp['errors']
        assert u'The narrow phonetic transcription you have entered is not valid' \
            in resp['errors']['narrowPhoneticTranscription']
        assert u'The morpheme segmentation you have entered is not valid' \
            in resp['errors']['morphemeBreak']
        assert formCount == 0

        # Now perform a successful create by making the narrow phonetic and
        # morpheme break fields valid according to the relevant inventories.
        params = self.createParams.copy()
        params.update({
            'narrowPhoneticTranscription': u'n p NP N P NNNN pPPP pnNpP   ',
            'phoneticTranscription': u'test broad phonetic transcription validation',
            'transcription': u'test orthographic transcription validation',
            'morphemeBreak': u'OOO ooo OOO   o',
            'glosses': [{'gloss': u'test validation gloss', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert u'errors' not in resp
        assert formCount == 1

        # Create a foreign word form (i.e., one tagged with a foreign word tag).
        # Such forms should be able to violate the inventory-based validation
        # restrictions.
        # We need to ensure that updateApplicationSettingsIfFormIsForeignWord
        # is updating the global Inventory objects with the foreign word.
        # The key 'test.applicationSettings' in the environ causes application
        # settings to be deleted from app_globals after each request; to prevent
        # this we pass in 'test.retainApplicationSettings' also.
        retain_extra_environ = extra_environ.copy()
        retain_extra_environ['test.retainApplicationSettings'] = True
        foreignWordTag = h.generateForeignWordTag()
        Session.add(foreignWordTag)
        Session.commit()
        params = self.createParams.copy()
        params.update({
            'narrowPhoneticTranscription': u'f`ore_n',
            'phoneticTranscription': u'foren',
            'transcription': u'foreign',
            'morphemeBreak': u'foreign',
            'glosses': [{'gloss': u'foreign gloss', 'glossGrammaticality': u''}],
            'tags': [h.getForeignWordTag().id]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 retain_extra_environ)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        applicationSettings = response.g.applicationSettings
        assert 'f`ore_n' in applicationSettings.narrowPhoneticInventory.inputList
        assert 'foren' in applicationSettings.broadPhoneticInventory.inputList
        assert 'foreign' in applicationSettings.morphemeBreakInventory.inputList
        assert 'foreign' in applicationSettings.orthographicInventory.inputList
        assert u'errors' not in resp
        assert formCount == 2

        # Now create a form that would violate inventory-based validation rules
        # but is nevertheless accepted because the violations are foreign words.
        params = self.createParams.copy()
        params.update({
            'narrowPhoneticTranscription': u'n f`ore_np',
            'phoneticTranscription': u'b p',
            'transcription': u'o O',
            'morphemeBreak': u'o-foreign-O',
            'glosses': [{'gloss': u'sentence containing foreign word', 'glossGrammaticality': u''}]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert u'errors' not in resp
        assert formCount == 3

    #@nottest
    def test_relational_attribute_creation(self):
        """Tests that POST/PUT create and update many-to-many data correctly."""

        formCount = Session.query(model.Form).count()

        # Add an empty application settings and two syntactic categories.
        restrictedTag = h.generateRestrictedTag()
        foreignWordTag = h.generateForeignWordTag()
        file1Name = u'test_relational_file'
        file2Name = u'test_relational_file_2'
        file1 = h.generateDefaultFile()
        file1.name = file1Name
        file2 = h.generateDefaultFile()
        file2.name = file2Name
        Session.add_all([restrictedTag, foreignWordTag,
                              file1, file2])
        Session.commit()

        # Create a form with some files and tags.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test relational transcription',
            'glosses': [{'gloss': u'test relational gloss',
                         'glossGrammaticality': u''}],
            'tags': [t.id for t in h.getTags()],
            'files': [f.id for f in h.getFiles()]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        newFormCount = Session.query(model.Form).count()
        resp = json.loads(response.body)
        formFiles = Session.query(model.FormFile)
        createdFormId = resp['id']
        assert newFormCount == formCount + 1
        assert len([ff.form_id for ff in formFiles
                    if ff.form_id == resp['id']]) == 2
        assert file1Name in [f['name'] for f in resp['files']]
        assert file2Name in [f['name'] for f in resp['files']]
        assert restrictedTag.name in [t['name'] for t in resp['tags']]

        # Attempt to update the form we just created but don't change the tags.
        # Expect the update attempt to fail.
        tags = [t.id for t in h.getTags()]
        tags.reverse()
        files = [f.id for f in h.getFiles()]
        files.reverse()
        params = self.createParams.copy()
        params.update({
            'transcription': u'test relational transcription',
            'glosses': [{'gloss': u'test relational gloss',
                         'glossGrammaticality': u''}],
            'tags': tags,
            'files': files
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=createdFormId), params,
                        self.json_headers, self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'The update request failed because the submitted data were not new.'

        # Now update by removing one of the files and expect success.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test relational transcription',
            'glosses': [{'gloss': u'test relational gloss',
                         'glossGrammaticality': u''}],
            'tags': tags,
            'files': files[0:1]
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=createdFormId), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        formCount = newFormCount
        newFormCount = Session.query(model.Form).count()
        assert newFormCount == formCount
        assert len(resp['files']) == 1
        assert restrictedTag.name in [t['name'] for t in resp['tags']]
        assert foreignWordTag.name in [t['name'] for t in resp['tags']]

        # Attempt to create a form with some *invalid* files and tags and fail.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test relational transcription invalid',
            'glosses': [{'gloss': u'test relational gloss invalid',
                         'glossGrammaticality': u''}],
            'tags': [1000, 9875, u'abcdef'],
            'files': [44, u'1t']
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin, status=400)
        formCount = newFormCount
        newFormCount = Session.query(model.Form).count()
        resp = json.loads(response.body)
        assert newFormCount == formCount
        assert u'Please enter an integer value' in resp['errors']['files']
        assert u'There is no file with id 44.' in resp['errors']['files']
        assert u'There is no tag with id 1000.' in resp['errors']['tags']
        assert u'There is no tag with id 9875.' in resp['errors']['tags']
        assert u'Please enter an integer value' in resp['errors']['tags']

    #@nottest
    def test_new(self):
        """Tests that GET /form/new returns an appropriate JSON object for creating a new OLD form.

        The properties of the JSON object are 'grammaticalities',
        'elicitationMethods', 'tags', 'syntacticCategories', 'speakers',
        'users', 'sources' and 'files' and their values are arrays/lists.
        """

        # Unauthorized user ('viewer') should return a 401 status code on the
        # new action, which requires a 'contributor' or an 'administrator'.
        extra_environ = {'test.authentication.role': 'viewer'}
        response = self.app.get(url('new_form'), extra_environ=extra_environ,
                                status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        elicitationMethod = h.generateDefaultElicitationMethod()
        foreignWordTag = h.generateForeignWordTag()
        restrictedTag = h.generateRestrictedTag()
        N = h.generateNSyntacticCategory()
        Num = h.generateNumSyntacticCategory()
        S = h.generateSSyntacticCategory()
        speaker = h.generateDefaultSpeaker()
        source = h.generateDefaultSource()
        file1 = h.generateDefaultFile()
        file1.name = u'file1'
        file2 = h.generateDefaultFile()
        file2.name = u'file2'
        Session.add_all([applicationSettings, elicitationMethod,
                    foreignWordTag, restrictedTag, N, Num, S, speaker, source,
                    file1, file2])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'grammaticalities': h.getGrammaticalities(),
            'elicitationMethods': h.getElicitationMethods(),
            'tags': h.getTags(),
            'syntacticCategories': h.getSyntacticCategories(),
            'speakers': h.getSpeakers(),
            'users': h.getUsers(),
            'sources': h.getSources(),
            'files': h.getFiles(),
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        # GET /form/new without params.  Without any GET params, /form/new
        # should return a JSON array for every store.
        response = self.app.get(url('new_form'),
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['grammaticalities'] == data['grammaticalities']
        assert resp['elicitationMethods'] == data['elicitationMethods']
        assert resp['tags'] == data['tags']
        assert resp['syntacticCategories'] == data['syntacticCategories']
        assert resp['speakers'] == data['speakers']
        assert resp['users'] == data['users']
        assert resp['sources'] == data['sources']
        assert resp['files'] == data['files']

        # GET /new_form with params.  Param values are treated as strings, not
        # JSON.  If any params are specified, the default is to return a JSON
        # array corresponding to store for the param.  There are three cases
        # that will result in an empty JSON array being returned:
        # 1. the param is not specified
        # 2. the value of the specified param is an empty string
        # 3. the value of the specified param is an ISO 8601 UTC datetime
        #    string that matches the most recent datetimeModified value of the
        #    store in question.
        params = {
            # Value is empty string: 'grammaticalities' will not be in response.
            'grammaticalities': '',
            # Value is any string: 'elicitationMethods' will be in response.
            'elicitationMethods': 'anything can go here!',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Tag.datetimeModified value: 'tags' *will* be in
            # response.
            'tags': datetime.datetime.utcnow().isoformat(),
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent SyntacticCategory.datetimeModified value:
            # 'syntacticCategories' will *not* be in response.
            'syntacticCategories': h.getMostRecentModificationDatetime(
                'SyntacticCategory').isoformat()
        }
        response = self.app.get(url('new_form'), params,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['elicitationMethods'] == data['elicitationMethods']
        assert resp['tags'] == data['tags']
        assert resp['grammaticalities'] == []
        assert resp['syntacticCategories'] == []
        assert resp['speakers'] == []
        assert resp['users'] == []
        assert resp['sources'] == []
        assert resp['files'] == []

    #@nottest
    def test_update(self):
        """Tests that PUT /forms/id correctly updates an existing form."""

        formCount = Session.query(model.Form).count()

        # Add the default application settings and the restricted tag.
        restrictedTag = h.generateRestrictedTag()
        applicationSettings = h.generateDefaultApplicationSettings()
        Session.add_all([applicationSettings, restrictedTag])
        Session.commit()
        restrictedTag = h.getRestrictedTag()

        # Create a form to update.
        params = self.createParams.copy()
        originalTranscription = u'test_update_transcription'
        originalGloss = u'test_update_gloss'
        params.update({
            'transcription': originalTranscription,
            'glosses': [{'gloss': originalGloss, 'glossGrammaticality': u''}],
            'tags': [restrictedTag.id]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        id = int(resp['id'])
        newFormCount = Session.query(model.Form).count()
        assert resp['transcription'] == originalTranscription
        assert resp['glosses'][0]['gloss'] == originalGloss
        assert newFormCount == formCount + 1

        # As a viewer, attempt to update the restricted form we just created.
        # Expect to fail.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'transcription': u'Updated!',
            'glosses': [{'gloss': u'test_update_gloss', 'glossGrammaticality': u''}],
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=id), params,
            self.json_headers, extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        # As an administrator now, update the form just created and expect to
        # succeed.
        origBackupCount = Session.query(model.FormBackup).count()
        params = self.createParams.copy()
        params.update({
            'transcription': u'Updated!',
            'glosses': [{'gloss': u'test_update_gloss', 'glossGrammaticality': u''}],
            'morphemeBreak': u'a-b',
            'morphemeGloss': u'c-d'
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=id), params,
                                self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        newFormCount = Session.query(model.Form).count()
        newBackupCount = Session.query(model.FormBackup).count()
        assert resp['transcription'] == u'Updated!'
        assert resp['glosses'][0]['gloss'] == u'test_update_gloss'
        assert resp['morphemeBreak'] == u'a-b'
        assert resp['morphemeGloss'] == u'c-d'
        assert resp['morphemeBreakIDs'] == [[[], []]]
        assert resp['morphemeGlossIDs'] == [[[], []]]
        assert newFormCount == formCount + 1
        assert origBackupCount + 1 == newBackupCount
        backup = Session.query(model.FormBackup).filter(
            model.FormBackup.UUID==unicode(
            resp['UUID'])).order_by(
            desc(model.FormBackup.id)).first()
        assert backup.datetimeModified.isoformat() == resp['datetimeModified']
        assert backup.transcription == originalTranscription

        # Attempt an update with no new data.  Expect a 400 error
        # and response['errors'] = {'no change': The update request failed
        # because the submitted data were not new.'}.
        origBackupCount = Session.query(model.FormBackup).count()
        response = self.app.put(url('form', id=id), params, self.json_headers,
                                self.extra_environ_admin, status=400)
        newBackupCount = Session.query(model.FormBackup).count()
        resp = json.loads(response.body)
        assert origBackupCount == newBackupCount
        assert u'the submitted data were not new' in resp['error']

        # Create a lexical form that will cause the morphemeBreakIDs and
        # morphemeGlossIDs attributes of the aforementioned form to change.  Now
        # an update with no new data will succeed -- simply because the lexicon
        # of the database has changed.
        origBackupCount = Session.query(model.FormBackup).count()
        newParams = self.createParams.copy()
        newParams.update({
            'transcription': u'a',
            'glosses': [{'gloss': u'lexical', 'glossGrammaticality': u''}],
            'morphemeBreak': u'a',
            'morphemeGloss': u'c'
        })
        newParams = json.dumps(newParams)
        response = self.app.post(url('forms'), newParams, self.json_headers,
                                 self.extra_environ_admin)
        response = self.app.put(url('form', id=id), params, self.json_headers,
                                self.extra_environ_admin)
        newBackupCount = Session.query(model.FormBackup).count()
        resp = json.loads(response.body)
        morphemeBreakIDs = resp['morphemeBreakIDs']
        morphemeGlossIDs = resp['morphemeGlossIDs']
        assert origBackupCount + 1 == newBackupCount
        assert resp['transcription'] == u'Updated!'
        assert resp['glosses'][0]['gloss'] == u'test_update_gloss'
        assert resp['morphemeBreak'] == u'a-b'
        assert resp['morphemeGloss'] == u'c-d'
        assert morphemeBreakIDs[0][0][0][1] == u'c'
        assert morphemeBreakIDs[0][0][0][2] == None
        assert morphemeGlossIDs[0][0][0][1] == u'a'
        assert morphemeGlossIDs[0][0][0][2] == None

        # Again update our form, this time making it into a foreign word.
        # Updating a form into a foreign word should update the Inventory
        # objects in app_globals.
        # First we create an application settings with some VERY STRICT
        # inventory-based validation settings.  Also we add a foreign word tag.
        orthography = model.Orthography()
        orthography.name = u'Test Orthography'
        orthography.orthography = u'o,O'
        orthography.lowercase = True
        orthography.initialGlottalStops = True
        Session.add(orthography)
        Session.commit()
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.orthographicValidation = u'Error'
        applicationSettings.narrowPhoneticInventory = u'n,p,N,P'
        applicationSettings.narrowPhoneticValidation = u'Error'
        applicationSettings.broadPhoneticInventory = u'b,p,B,P'
        applicationSettings.broadPhoneticValidation = u'Error'
        applicationSettings.morphemeBreakIsOrthographic = False
        applicationSettings.morphemeBreakValidation = u'Error'
        applicationSettings.phonemicInventory = u'p,i,P,I'
        applicationSettings.storageOrthography = h.getOrthographies()[0]
        foreignWordTag = h.generateForeignWordTag()
        Session.add_all([applicationSettings, foreignWordTag])
        Session.commit()
        # Here we indirectly cause app_globals.applicationSettings to be set to
        # an h.ApplicationSettings instance that has our model.ApplicationSettings
        # instance as an attribute.  We do this with some special keys in environ.
        # We need to ensure that updateApplicationSettingsIfFormIsForeignWord
        # is updating the global Inventory objects with the foreign word.
        # The key 'test.applicationSettings' in the environ causes application
        # settings to be deleted from app_globals after each request; to prevent
        # this we pass in 'test.retainApplicationSettings' also.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        extra_environ['test.retainApplicationSettings'] = True
        # Now we update using the same params as before, only this time we tag
        # as a foreign word.  
        params = self.createParams.copy()
        params.update({
            'transcription': u'Updated!',
            'glosses': [{'gloss': u'test_update_gloss', 'glossGrammaticality': u''}],
            'tags': [h.getForeignWordTag().id],
            'morphemeBreak': u'a-b',
            'morphemeGloss': u'c-d'
        })
        params = json.dumps(params)
        # There should be no app_globals.applicationSettings in the last response.
        assert not hasattr(response.g, 'applicationSettings')
        response = self.app.put(url('form', id=id), params, self.json_headers,
                                extra_environ)
        resp = json.loads(response.body)
        applicationSettings = response.g.applicationSettings
        # This is how we know that updateApplicationSettingsIfFormIsForeignWord
        # is working
        assert 'a-b' in applicationSettings.morphemeBreakInventory.inputList
        assert 'Updated!' in applicationSettings.orthographicInventory.inputList
        assert u'errors' not in resp

        # Now update our form by adding a many-to-one datum, viz. a speaker
        speaker = h.generateDefaultSpeaker()
        Session.add(speaker)
        Session.commit()
        speaker = h.getSpeakers()[0]
        params = self.createParams.copy()
        params.update({
            'transcription': u'oO',
            'glosses': [{'gloss': 'Updated again gloss',
                         'glossGrammaticality': u''}],
            'speaker': speaker.id,
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=id), params, self.json_headers,
                                 extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert resp['speaker']['firstName'] == speaker.firstName

    #@nottest
    def test_delete(self):
        """Tests that DELETE /forms/id deletes the form with id=id and returns a JSON representation.

        If the id is invalid or unspecified, then JSON null or a 404 status code
        are returned, respectively.
        """

        # Add the default application settings and a default speaker.
        applicationSettings = h.generateDefaultApplicationSettings()
        speaker = h.generateDefaultSpeaker()
        myContributor = h.generateDefaultUser()
        myContributor.username = u'uniqueusername'
        Session.add_all([applicationSettings, speaker, myContributor])
        Session.commit()
        myContributor = Session.query(model.User).filter(
            model.User.username==u'uniqueusername').first()
        myContributorId = myContributor.id

        # Count the original number of forms and formBackups.
        formCount = Session.query(model.Form).count()
        formBackupCount = Session.query(model.FormBackup).count()

        # First, as myContributor, create a form to delete.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        speaker = Session.query(model.Speaker).first()
        speakerFirstName = speaker.firstName
        params = self.createParams.copy()
        params.update({
            'transcription': u'test_delete_transcription',
            'glosses': [{'gloss': u'test_delete_gloss', 'glossGrammaticality': u''}],
            'speaker': unicode(speaker.id)
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        toDeleteId = resp['id']
        assert resp['transcription'] == u'test_delete_transcription'
        assert resp['glosses'][0]['gloss'] == u'test_delete_gloss'

        # Now count the forms and formBackups.
        newFormCount = Session.query(model.Form).count()
        newFormBackupCount = Session.query(model.FormBackup).count()
        assert newFormCount == formCount + 1
        assert newFormBackupCount == formBackupCount

        # Now, as the default contributor, attempt to delete the myContributor-
        # entered form we just created and expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.applicationSettings': True}
        response = self.app.delete(url('form', id=toDeleteId),
                                   extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        # As myContributor, attempt to delete the form we just created and
        # expect to succeed.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.delete(url('form', id=toDeleteId),
                                   extra_environ=extra_environ)
        resp = json.loads(response.body)
        newFormCount = Session.query(model.Form).count()
        newFormBackupCount = Session.query(model.FormBackup).count()
        glossOfDeletedForm = Session.query(model.Gloss).get(
            resp['glosses'][0]['id'])
        assert glossOfDeletedForm is None
        assert newFormCount == formCount
        assert newFormBackupCount == formBackupCount + 1

        # The deleted form will be returned to us, so the assertions from above
        # should still hold true.
        assert resp['transcription'] == u'test_delete_transcription'
        assert resp['glosses'][0]['gloss'] == u'test_delete_gloss'

        # Trying to get the deleted form from the db should return None
        deletedForm = Session.query(model.Form).get(toDeleteId)
        assert deletedForm == None

        # The backed up form should have the deleted form's attributes
        backedUpForm = Session.query(model.FormBackup).filter(
            model.FormBackup.UUID==unicode(resp['UUID'])).first()
        assert backedUpForm.transcription == resp['transcription']
        backuper = json.loads(unicode(backedUpForm.backuper))
        assert backuper['firstName'] == u'test user first name'
        backedUpSpeaker = json.loads(unicode(backedUpForm.speaker))
        assert backedUpSpeaker['firstName'] == speakerFirstName
        assert backedUpForm.datetimeEntered.isoformat() == resp['datetimeEntered']
        assert backedUpForm.UUID == resp['UUID']

        # Delete with an invalid id
        id = 9999999999999
        response = self.app.delete(url('form', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no form with id %s' % id in json.loads(response.body)[
            'error']

        # Delete without an id
        response = self.app.delete(url('form', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

    #@nottest
    def test_delete_foreign_word(self):
        """Tests that DELETE /forms/id on a foreign word updates the global Inventory objects correctly."""

        # First create an application settings with some VERY STRICT
        # inventory-based validation settings and a foreign word tag.
        orthography = model.Orthography()
        orthography.name = u'Test Orthography'
        orthography.orthography = u'o,O'
        orthography.lowercase = True
        orthography.initialGlottalStops = True
        Session.add(orthography)
        Session.commit()
        applicationSettings = h.generateDefaultApplicationSettings()
        applicationSettings.orthographicValidation = u'Error'
        applicationSettings.narrowPhoneticInventory = u'n,p,N,P'
        applicationSettings.narrowPhoneticValidation = u'Error'
        applicationSettings.broadPhoneticInventory = u'b,p,B,P'
        applicationSettings.broadPhoneticValidation = u'Error'
        applicationSettings.morphemeBreakIsOrthographic = False
        applicationSettings.morphemeBreakValidation = u'Error'
        applicationSettings.phonemicInventory = u'p,i,P,I'
        applicationSettings.storageOrthography = h.getOrthographies()[0]
        foreignWordTag = h.generateForeignWordTag()
        Session.add_all([applicationSettings, foreignWordTag])
        Session.commit()

        # The extra_environ request param causes app_globals.applicationSettings to be set to
        # an h.ApplicationSettings instance that has our model.ApplicationSettings
        # instance as an attribute.  We do this with some special keys in environ.
        # We need to ensure that updateApplicationSettingsIfFormIsForeignWord
        # is updating the global Inventory objects with the foreign word.
        # The key 'test.applicationSettings' in the environ causes application
        # settings to be deleted from app_globals after each request; to prevent
        # this we pass in 'test.retainApplicationSettings' also.
        extra_environ = self.extra_environ_admin.copy()
        extra_environ['test.applicationSettings'] = True
        extra_environ['test.retainApplicationSettings'] = True

        # Then create a foreign word form to delete.
        params = self.createParams.copy()
        params.update({
            'transcription': u'test_delete_transcription',
            'glosses': [{'gloss': u'test_delete_gloss', 'glossGrammaticality': u''}],
            'tags': [h.getForeignWordTag().id]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                                 extra_environ)
        resp = json.loads(response.body)
        assert hasattr(response.g, 'applicationSettings')
        applicationSettings = response.g.applicationSettings
        assert resp['transcription'] == u'test_delete_transcription'
        assert resp['glosses'][0]['gloss'] == u'test_delete_gloss'
        assert 'test_delete_transcription' in applicationSettings.orthographicInventory.inputList

        # Delete the form we just created and observe that the orthographic
        # transcription has been removed from the orthographicInventory object.
        response = self.app.delete(url('form', id=resp['id']),
                                   extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert hasattr(response.g, 'applicationSettings')
        applicationSettings = response.g.applicationSettings
        assert 'test_delete_transcription' not in applicationSettings.orthographicInventory.inputList

    #@nottest
    def test_show(self):
        """Tests that GET /forms/id returns a JSON form object, null or 404
        depending on whether the id is valid, invalid or unspecified,
        respectively.
        """

        # First add a form.
        form = h.generateDefaultForm()
        Session.add(form)
        Session.commit()
        formId = h.getForms()[0].id

        # Invalid id
        id = 100000000000
        response = self.app.get(url('form', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        resp = json.loads(response.body)
        assert u'There is no form with id %s' % id in json.loads(response.body)[
            'error']

        # No id
        response = self.app.get(url('form', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Valid id
        response = self.app.get(url('form', id=formId), headers=self.json_headers,
                                extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['transcription'] == u'test transcription'
        assert resp['glosses'][0]['gloss'] == u'test gloss'

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
        # Finally, issue a POST request to create the restricted form with
        # the *default* contributor as the enterer.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'transcription': u'test restricted tag transcription',
            'glosses': [{'gloss': u'test restricted tag gloss',
                         'glossGrammaticality': u''}],
            'tags': [h.getTags()[0].id]    # the restricted tag should be the only one
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                        extra_environ)
        resp = json.loads(response.body)
        restrictedFormId = resp['id']
        # Expectation: the administrator, the default contributor (qua enterer)
        # and the unrestricted myContributor should all be able to view the form.
        # The viewer should get a 403 error when attempting to view this form.
        # An administrator should be able to view this form.
        extra_environ = {'test.authentication.role': 'administrator',
                         'test.applicationSettings': True}
        response = self.app.get(url('form', id=restrictedFormId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # The default contributor (qua enterer) should be able to view this form.
        extra_environ = {'test.authentication.id': contributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('form', id=restrictedFormId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # Mycontributor (an unrestricted user) should be able to view this
        # restricted form.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('form', id=restrictedFormId),
                        headers=self.json_headers, extra_environ=extra_environ)
        # A (not unrestricted) viewer should *not* be able to view this form.
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('form', id=restrictedFormId),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        # Remove Mycontributor from the unrestricted users list and access will be denied.
        applicationSettings = h.getApplicationSettings()
        applicationSettings.unrestrictedUsers = []
        Session.add(applicationSettings)
        Session.commit()
        # Mycontributor (no longer an unrestricted user) should now *not* be
        # able to view this restricted form.
        extra_environ = {'test.authentication.id': myContributorId,
                         'test.applicationSettings': True}
        response = self.app.get(url('form', id=restrictedFormId),
            headers=self.json_headers, extra_environ=extra_environ, status=403)
        # Remove the restricted tag from the form and the viewer should now be
        # able to view it too.
        restrictedForm = Session.query(model.Form).get(restrictedFormId)
        restrictedForm.tags = []
        Session.add(restrictedForm)
        Session.commit()
        extra_environ = {'test.authentication.role': 'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(url('form', id=restrictedFormId),
                        headers=self.json_headers, extra_environ=extra_environ)

    #@nottest
    def test_edit(self):
        """Tests that GET /forms/id/edit returns a JSON object of data necessary to edit the form with id=id.
        
        The JSON object is of the form {'form': {...}, 'data': {...}} or
        {'error': '...'} (with a 404 status code) depending on whether the id is
        valid or invalid/unspecified, respectively.
        """

        # Add the default application settings and the restricted tag.
        applicationSettings = h.generateDefaultApplicationSettings()
        restrictedTag = h.generateRestrictedTag()
        Session.add_all([restrictedTag, applicationSettings])
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        # Create a restricted form.
        form = h.generateDefaultForm()
        form.tags = [restrictedTag]
        Session.add(form)
        Session.commit()
        restrictedForm = h.getForms()[0]
        restrictedFormId = restrictedForm.id

        # As a (not unrestricted) contributor, attempt to call edit on the
        # restricted form and expect to fail.
        extra_environ = {'test.authentication.role': 'contributor',
                         'test.applicationSettings': True}
        response = self.app.get(url('edit_form', id=restrictedFormId),
                                extra_environ=extra_environ, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        # Not logged in: expect 401 Unauthorized
        response = self.app.get(url('edit_form', id=restrictedFormId), status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'

        # Invalid id
        id = 9876544
        response = self.app.get(url('edit_form', id=id),
            headers=self.json_headers, extra_environ=self.extra_environ_admin,
            status=404)
        assert u'There is no form with id %s' % id in json.loads(response.body)[
            'error']

        # No id
        response = self.app.get(url('edit_form', id=''), status=404,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert json.loads(response.body)['error'] == \
            'The resource could not be found.'

        # Valid id
        response = self.app.get(url('edit_form', id=restrictedFormId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['form']['transcription'] == u'test transcription'
        assert resp['form']['glosses'][0]['gloss'] == u'test gloss'

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
        elicitationMethod = h.generateDefaultElicitationMethod()
        foreignWordTag = h.generateForeignWordTag()
        N = h.generateNSyntacticCategory()
        Num = h.generateNumSyntacticCategory()
        S = h.generateSSyntacticCategory()
        speaker = h.generateDefaultSpeaker()
        source = h.generateDefaultSource()
        file1 = h.generateDefaultFile()
        file1.name = u'file1'
        file2 = h.generateDefaultFile()
        file2.name = u'file2'
        Session.add_all([applicationSettings, elicitationMethod,
            foreignWordTag, N, Num, S, speaker, source, file1, file2])
        Session.commit()

        # Get the data currently in the db (see websetup.py for the test data).
        data = {
            'grammaticalities': h.getGrammaticalities(),
            'elicitationMethods': h.getElicitationMethods(),
            'tags': h.getTags(),
            'syntacticCategories': h.getSyntacticCategories(),
            'speakers': h.getSpeakers(),
            'users': h.getUsers(),
            'sources': h.getSources(),
            'files': h.getFiles()
        }
        # JSON.stringify and then re-Python-ify the data.  This is what the data
        # should look like in the response to a simulated GET request.
        data = json.loads(json.dumps(data, cls=h.JSONOLDEncoder))

        params = {
            # Value is a non-empty string: 'grammaticalities' will be in response.
            'grammaticalities': 'give me some grammaticalities!',
            # Value is empty string: 'elicitationMethods' will not be in response.
            'elicitationMethods': '',
            # Value is ISO 8601 UTC datetime string that does not match the most
            # recent Source.datetimeModified value: 'sources' *will* be in
            # response.
            'sources': datetime.datetime.utcnow().isoformat(),
            # Value is ISO 8601 UTC datetime string that does match the most
            # recent User.datetimeModified value: 'users' will *not* be in response.
            'users': h.getMostRecentModificationDatetime('User').isoformat()
        }
        response = self.app.get(url('edit_form', id=restrictedFormId), params,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['data']['elicitationMethods'] == []
        assert resp['data']['tags'] == []
        assert resp['data']['grammaticalities'] == data['grammaticalities']
        assert resp['data']['syntacticCategories'] == []
        assert resp['data']['speakers'] == []
        assert resp['data']['users'] == []
        assert resp['data']['sources'] == data['sources']
        assert resp['data']['files'] == []

        # Invalid id with GET params.  It should still return 'null'.
        params = {
            # If id were valid, this would cause a speakers array to be returned
            # also.
            'speakers': 'True',
        }
        response = self.app.get(url('edit_form', id=id), params,
                            extra_environ=self.extra_environ_admin, status=404)
        assert u'There is no form with id %s' % id in json.loads(response.body)[
            'error']

    #@nottest
    def test_history(self):
        """Tests that GET /forms/id/history returns the form with id=id and its previous incarnations.
        
        The JSON object returned is of the form
        {'form': form, 'previousVersions': [...]}.
        """

        # Add some test data to the database.
        applicationSettings = h.generateDefaultApplicationSettings()
        elicitationMethod = h.generateDefaultElicitationMethod()
        source = h.generateDefaultSource()
        restrictedTag = h.generateRestrictedTag()
        foreignWordTag = h.generateForeignWordTag()
        file1 = h.generateDefaultFile()
        file1.name = u'file1'
        file2 = h.generateDefaultFile()
        file2.name = u'file2'
        N = h.generateNSyntacticCategory()
        Num = h.generateNumSyntacticCategory()
        S = h.generateSSyntacticCategory()
        speaker = h.generateDefaultSpeaker()
        Session.add_all([applicationSettings, elicitationMethod, source,
            restrictedTag, foreignWordTag, file1, file2, N, Num, S, speaker])
        Session.commit()

        # Create a restricted form (via request) as the default contributor
        users = h.getUsers()
        contributorId = [u for u in users if u.role==u'contributor'][0].id
        administratorId = [u for u in users if u.role==u'administrator'][0].id
        speakerId = h.getSpeakers()[0].id
        elicitationMethodId = h.getElicitationMethods()[0].id
        syntacticCategoryIds = [sc.id for sc in h.getSyntacticCategories()]
        firstSyntacticCategoryId = syntacticCategoryIds[0]
        lastSyntacticCategoryId = syntacticCategoryIds[-1]
        tagIds = [t.id for t in h.getTags()]
        fileIds = [f.id for f in h.getFiles()]
        restrictedTagId = h.getRestrictedTag().id

        extra_environ = {'test.authentication.role': u'contributor',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'transcription': u'created by the contributor',
            'glosses': [{'gloss': u'created by the contributor', 'glossGrammaticality': u''}],
            'elicitor': contributorId,
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                        extra_environ)
        formCount = Session.query(model.Form).count()
        resp = json.loads(response.body)
        formId = resp['id']
        formUUID = resp['UUID']
        assert formCount == 1

        # Update our form (via request) as the default administrator
        extra_environ = {'test.authentication.role': u'administrator',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'grammaticality': u'?',
            'transcription': u'updated by the administrator',
            'glosses': [{'gloss': u'updated by the administrator',
                         'glossGrammaticality': u'*'}],
            'morphemeBreak': u'up-dat-ed by the ad-ministr-ator',
            'morphemeGloss': u'up-date-PAST PREP DET PREP-servant-AGT',
            'speaker': speakerId,
            'elicitationMethod': elicitationMethodId,
            'syntacticCategory': firstSyntacticCategoryId,
            'verifier': administratorId,
            'tags': tagIds + [None, u''], # None and u'' ('') will be ignored by forms.updateForm
            'enterer': administratorId  # This should change nothing.
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=formId), params,
                        self.json_headers, extra_environ)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert formCount == 1

        # Finally, update our form (via request) as the default contributor.
        extra_environ = {'test.authentication.role': u'contributor',
                         'test.applicationSettings': True}
        params = self.createParams.copy()
        params.update({
            'grammaticality': u'#',
            'transcription': u'updated by the contributor',
            'glosses': [{'gloss': u'updated by the contributor',
                         'glossGrammaticality': u'*'}],
            'morphemeBreak': u'up-dat-ed by the ad-ministr-ator',
            'morphemeGloss': u'up-date-PAST PREP DET PREP-servant-AGT',
            'speaker': speakerId,
            'elicitationMethod': elicitationMethodId,
            'syntacticCategory': lastSyntacticCategoryId,
            'tags': tagIds,
            'files': fileIds
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=formId), params,
                        self.json_headers, extra_environ)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        assert formCount == 1

        # Now get the history of this form.
        extra_environ = {'test.authentication.role': u'contributor',
                         'test.applicationSettings': True}
        response = self.app.get(
            url(controller='forms', action='history', id=formId),
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert 'form' in resp
        assert 'previousVersions' in resp
        firstVersion = resp['previousVersions'][1]
        secondVersion = resp['previousVersions'][0]
        currentVersion = resp['form']
        assert firstVersion['transcription'] == u'created by the contributor'
        assert firstVersion['morphemeBreak'] == u''
        assert firstVersion['elicitor']['id'] == contributorId
        assert firstVersion['enterer']['id'] == contributorId
        assert firstVersion['backuper']['id'] == administratorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert firstVersion['datetimeModified'] <= secondVersion['datetimeModified']
        assert firstVersion['speaker'] == None
        assert firstVersion['elicitationMethod'] == None
        assert firstVersion['syntacticCategory'] == None
        assert firstVersion['verifier'] == None
        assert [t['id'] for t in firstVersion['tags']] == [restrictedTagId]
        assert firstVersion['files'] == []
        assert firstVersion['morphemeBreakIDs'] == [[[]]]

        assert secondVersion['transcription'] == u'updated by the administrator'
        assert secondVersion['morphemeBreak'] == u'up-dat-ed by the ad-ministr-ator'
        assert secondVersion['elicitor'] == None
        assert secondVersion['enterer']['id'] == contributorId
        assert secondVersion['backuper']['id'] == contributorId
        assert secondVersion['datetimeModified'] == currentVersion['datetimeModified']
        assert secondVersion['speaker']['id'] == speakerId
        assert secondVersion['elicitationMethod']['id'] == elicitationMethodId
        assert secondVersion['syntacticCategory']['id'] == firstSyntacticCategoryId
        assert secondVersion['verifier']['id'] == administratorId
        assert sorted([t['id'] for t in secondVersion['tags']]) == sorted(tagIds)
        assert secondVersion['files'] == []
        assert len(secondVersion['morphemeBreakIDs']) == 4

        assert currentVersion['transcription'] == u'updated by the contributor'
        assert currentVersion['morphemeBreak'] == u'up-dat-ed by the ad-ministr-ator'
        assert currentVersion['elicitor'] == None
        assert currentVersion['enterer']['id'] == contributorId
        assert 'backuper' not in currentVersion
        assert currentVersion['speaker']['id'] == speakerId
        assert currentVersion['elicitationMethod']['id'] == elicitationMethodId
        assert currentVersion['syntacticCategory']['id'] == lastSyntacticCategoryId
        assert currentVersion['verifier'] == None
        assert sorted([t['id'] for t in currentVersion['tags']]) == sorted(tagIds)
        assert sorted([f['id'] for f in currentVersion['files']]) == sorted(fileIds)
        assert len(currentVersion['morphemeBreakIDs']) == 4

        # Attempt to get the history of the just-entered restricted form as a
        # viewer and expect to fail with 403.
        extra_environ_viewer = {'test.authentication.role': u'viewer',
                         'test.applicationSettings': True}
        response = self.app.get(
            url(controller='forms', action='history', id=formId),
            headers=self.json_headers, extra_environ=extra_environ_viewer,
            status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'

        # Attempt to call history with an invalid id and an invalid UUID and
        # expect 404 errors in both cases.
        badId = 103
        badUUID = str(uuid4())
        response = self.app.get(
            url(controller='forms', action='history', id=badId),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No forms or form backups match %d' % badId
        response = self.app.get(
            url(controller='forms', action='history', id=badUUID),
            headers=self.json_headers, extra_environ=extra_environ,
            status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No forms or form backups match %s' % badUUID

        # Now delete the form ...
        response = self.app.delete(url('form', id=formId),
                        headers=self.json_headers, extra_environ=extra_environ)

        # ... and get its history again, this time using the form's UUID
        response = self.app.get(
            url(controller='forms', action='history', id=formUUID),
            headers=self.json_headers, extra_environ=extra_environ)
        byUUIDResp = json.loads(response.body)
        assert byUUIDResp['form'] == None
        assert len(byUUIDResp['previousVersions']) == 3
        firstVersion = byUUIDResp['previousVersions'][2]
        secondVersion = byUUIDResp['previousVersions'][1]
        thirdVersion = byUUIDResp['previousVersions'][0]
        assert firstVersion['transcription'] == u'created by the contributor'
        assert firstVersion['morphemeBreak'] == u''
        assert firstVersion['elicitor']['id'] == contributorId
        assert firstVersion['enterer']['id'] == contributorId
        assert firstVersion['backuper']['id'] == administratorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert firstVersion['datetimeModified'] <= secondVersion['datetimeModified']
        assert firstVersion['speaker'] == None
        assert firstVersion['elicitationMethod'] == None
        assert firstVersion['syntacticCategory'] == None
        assert firstVersion['verifier'] == None
        assert [t['id'] for t in firstVersion['tags']] == [restrictedTagId]
        assert firstVersion['files'] == []
        assert firstVersion['morphemeBreakIDs'] == [[[]]]

        assert secondVersion['transcription'] == u'updated by the administrator'
        assert secondVersion['morphemeBreak'] == u'up-dat-ed by the ad-ministr-ator'
        assert secondVersion['elicitor'] == None
        assert secondVersion['enterer']['id'] == contributorId
        assert secondVersion['backuper']['id'] == contributorId
        # Should be <; however, MySQL<5.6.4 does not support microseconds in datetimes 
        # so the test will fail/be inconsistent with <
        assert secondVersion['datetimeModified'] <= thirdVersion['datetimeModified']
        assert secondVersion['speaker']['id'] == speakerId
        assert secondVersion['elicitationMethod']['id'] == elicitationMethodId
        assert secondVersion['syntacticCategory']['id'] == firstSyntacticCategoryId
        assert secondVersion['verifier']['id'] == administratorId
        assert sorted([t['id'] for t in secondVersion['tags']]) == sorted(tagIds)
        assert secondVersion['files'] == []
        assert len(secondVersion['morphemeBreakIDs']) == 4

        assert thirdVersion['transcription'] == u'updated by the contributor'
        assert thirdVersion['morphemeBreak'] == u'up-dat-ed by the ad-ministr-ator'
        assert thirdVersion['elicitor'] == None
        assert thirdVersion['enterer']['id'] == contributorId
        assert 'backuper' in thirdVersion
        assert thirdVersion['speaker']['id'] == speakerId
        assert thirdVersion['elicitationMethod']['id'] == elicitationMethodId
        assert thirdVersion['syntacticCategory']['id'] == lastSyntacticCategoryId
        assert thirdVersion['verifier'] == None
        assert sorted([t['id'] for t in thirdVersion['tags']]) == sorted(tagIds)
        assert sorted([f['id'] for f in thirdVersion['files']]) == sorted(fileIds)
        assert len(thirdVersion['morphemeBreakIDs']) == 4

        # Get the deleted form's history again, this time using its id.  The 
        # response should be the same as the response received using the UUID.
        response = self.app.get(
            url(controller='forms', action='history', id=formId),
            headers=self.json_headers, extra_environ=extra_environ)
        byFormIdResp = json.loads(response.body)
        assert byFormIdResp == byUUIDResp

        # Create a new restricted form as an administrator.
        params = self.createParams.copy()
        params.update({
            'transcription': u'2nd form restricted',
            'glosses': [{'gloss': u'2nd form restricted',
                         'glossGrammaticality': u''}],
            'tags': [restrictedTagId]
        })
        params = json.dumps(params)
        response = self.app.post(url('forms'), params, self.json_headers,
                        self.extra_environ_admin)
        resp = json.loads(response.body)
        formCount = Session.query(model.Form).count()
        formId = resp['id']
        formUUID = resp['UUID']
        assert formCount == 1

        # Update the just-created form by removing the restricted tag.
        params = self.createParams.copy()
        params.update({
            'transcription': u'2nd form unrestricted',
            'glosses': [{'gloss': u'2nd form unrestricted', 'glossGrammaticality': u''}],
            'tags': []
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=formId), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        # Now update it in another way.
        params = self.createParams.copy()
        params.update({
            'transcription': u'2nd form unrestricted updated',
            'glosses': [{'gloss': u'2nd form unrestricted updated',
                         'glossGrammaticality': u''}],
            'tags': []
        })
        params = json.dumps(params)
        response = self.app.put(url('form', id=formId), params,
                        self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)

        # Get the history of the just-entered restricted form as a
        # contributor and expect to receive only the '2nd form' version in the
        # previousVersions.
        response = self.app.get(
            url(controller='forms', action='history', id=formId),
            headers=self.json_headers, extra_environ=extra_environ)
        resp = json.loads(response.body)
        assert len(resp['previousVersions']) == 1
        assert resp['previousVersions'][0]['transcription'] == \
            u'2nd form unrestricted'
        assert resp['form']['transcription'] == u'2nd form unrestricted updated'

        # Now get the history of the just-entered restricted form as an
        # administrator and expect to receive both backups.
        response = self.app.get(
            url(controller='forms', action='history', id=formId),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp['previousVersions']) == 2
        assert resp['previousVersions'][0]['transcription'] == \
            u'2nd form unrestricted'
        assert resp['previousVersions'][1]['transcription'] == \
            u'2nd form restricted'
        assert resp['form']['transcription'] == u'2nd form unrestricted updated'

    #@nottest
    def test_remember(self):
        """Tests that POST /forms/remember correctly saves the input list of forms to the logged in user's rememberedForms list.
        """
        # First create three forms, and restrict the first one.
        restrictedTag = h.generateRestrictedTag()
        form1 = h.generateDefaultForm()
        form2 = h.generateDefaultForm()
        form3 = h.generateDefaultForm()
        form1.transcription = u'form1'
        form2.transcription = u'form2'
        form3.transcription = u'form3'
        Session.add_all([form1, form2, form3, restrictedTag])
        Session.commit()
        restrictedTag = h.getRestrictedTag()
        form1.tags = [restrictedTag]
        Session.add(form1)
        Session.commit()
        forms = h.getForms()
        formIds = [form.id for form in forms]
        form1Id = [f.id for f in forms if f.transcription == u'form1'][0]
        formIdsSet = set(formIds)

        # Then try to remember all of these forms.  Send a JSON array of form
        # ids to remember and expect to get it back.
        params = json.dumps({'forms': formIds})
        response = self.app.post(url(controller='forms', action='remember'),
            params, headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(formIds)
        assert formIdsSet == set(resp)
        administrator = Session.query(model.User).filter(
            model.User.role==u'administrator').first()
        assert formIdsSet == set([f.id for f in administrator.rememberedForms])

        # A non-int-able form id in the input will result in a 400 error.
        badParams = formIds[:]
        badParams.append('a')
        badParams = json.dumps({'forms': badParams})
        response = self.app.post(url(controller='forms', action='remember'),
            badParams, headers=self.json_headers,
            extra_environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'Please enter an integer value' in resp['errors']['forms']

        # One nonexistent form id will return a 400 error.
        badId = 1000
        badParams = formIds[:]
        badParams.append(badId)
        badParams = json.dumps({'forms': badParams})
        response = self.app.post(url(controller='forms', action='remember'),
            badParams, headers=self.json_headers,
            extra_environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert u'There is no form with id %d.' % badId in resp['errors']['forms']

        # Bad JSON parameters will return its own 400 error.
        badJSON = u'[%d, %d, %d' % tuple(formIds)
        response = self.app.post(url(controller='forms', action='remember'),
            badJSON, headers=self.json_headers,
            extra_environ=self.extra_environ_admin, status=400)
        resp = json.loads(response.body)
        assert resp['error'] == \
            u'JSON decode error: the parameters provided were not valid JSON.'

        # An empty list ...
        emptyList = json.dumps([])
        response = self.app.post(url(controller='forms', action='remember'),
            emptyList, headers=self.json_headers,
            extra_environ=self.extra_environ_admin, status=404)
        resp = json.loads(response.body)
        assert resp['error'] == u'No valid form ids were provided.'

        # Re-issue the same remember request that succeeded previously.  Expect
        # user.rememberedForms to be unchanged (i.e., auto-duplicate removal)
        params = json.dumps({'forms': formIds})
        response = self.app.post(url(controller='forms', action='remember'),
            params, headers=self.json_headers,
            extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert len(resp) == len(formIds)
        assert formIdsSet == set(resp)
        administrator = Session.query(model.User).filter(
            model.User.role==u'administrator').first()
        assert formIdsSet == set([f.id for f in administrator.rememberedForms])
        userForms = Session.query(model.UserForm).filter(
            model.UserForm.user_id==administrator.id).all()
        assert len(userForms) == len(formIds)

        # Now again issue the same remember request that succeeded previously
        # but this time as a restricted user, a viewer.  Expect only 2 forms
        # returned.
        extra_environ_viewer = {'test.authentication.role': u'viewer'}
        params = json.dumps({'forms': formIds})
        response = self.app.post(url(controller='forms', action='remember'),
            params, headers=self.json_headers,
            extra_environ=extra_environ_viewer)
        resp = json.loads(response.body)
        assert len(resp) == len(formIds) - 1
        assert form1Id not in resp
        viewer = Session.query(model.User).filter(
            model.User.role==u'viewer').first()
        assert len(resp) == len(viewer.rememberedForms)
        assert form1Id not in [f.id for id in viewer.rememberedForms]

        # Finally, request to remember only the restricted form as a viewer.
        # Expect a 403 error.
        params = json.dumps({'forms': [form1Id]})
        response = self.app.post(url(controller='forms', action='remember'),
            params, headers=self.json_headers,
            extra_environ=extra_environ_viewer, status=403)
        resp = json.loads(response.body)
        assert resp['error'] == u'You are not authorized to access this resource.'
        viewer = Session.query(model.User).filter(
            model.User.role==u'viewer').first()
        assert len(viewer.rememberedForms) == 2
        assert form1Id not in [f.id for id in viewer.rememberedForms]
