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
import datetime
import re
import simplejson as json
from uuid import uuid4

from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc, or_
from sqlalchemy.orm import subqueryload
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import FormSchema, FormIdsSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Form, FormBackup, Translation, User, Collection
from onlinelinguisticdatabase.controllers.oldcollections import updateCollectionByDeletionOfReferencedForm

log = logging.getLogger(__name__)

class FormsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol."""

    queryBuilder = SQLAQueryBuilder(config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """SEARCH /forms: Return all forms matching the filter passed as JSON in
        the request body.  Note: POST /forms/search also routes to this action.
        The request body must be a JSON object with a 'query' attribute; a
        'paginator' attribute is optional.  The 'query' object is passed to the
        getSQLAQuery() method of an SQLAQueryBuilder instance and an SQLA query
        is returned or an error is raised.  The 'query' object requires a
        'filter' attribute; an 'orderBy' attribute is optional.
        """
        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            SQLAQuery = self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query'))
            query = h.eagerloadForm(SQLAQuery)
            query = h.filterRestrictedModels('Form', SQLAQuery)
            return h.addPagination(query, pythonSearchParams.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except Exception, e:
            log.warn("%s's filter expression (%s) raised an unexpected exception: %s." % (
                h.getUserFullName(session['user']), request.body, e))
            response.status_int = 400
            return {'error': u'The specified search parameters generated an invalid database query'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """GET /forms/new_search: Return the data necessary to inform a search
        on the forms resource.
        """
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /forms: Return all forms."""
        try:
            query = h.eagerloadForm(Session.query(Form))
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels('Form', query)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """POST /forms: Create a new form."""
        try:
            schema = FormSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.getStateObject(values)
            data = schema.to_python(values, state)
            form = createNewForm(data)
            Session.add(form)
            Session.commit()
            updateApplicationSettingsIfFormIsForeignWord(form)
            updateFormsContainingThisFormAsMorpheme(form)
            return form
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """GET /new_form: Return the data necessary to create a new OLD form.

        Return a JSON object with the following properties: 'grammaticalities',
        'elicitationMethods', 'tags', 'syntacticCategories', 'speakers',
        'users' and 'sources', the value of each of which is an array that is
        either empty or contains the appropriate objects.

        See the getNewEditFormData function to understand how the GET params can
        affect the contents of the arrays.
        """
        return getNewEditFormData(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /forms/id: Update an existing form."""
        form = h.eagerloadForm(Session.query(Form)).get(int(id))
        if form:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, form, unrestrictedUsers):
                try:
                    schema = FormSchema()
                    values = json.loads(unicode(request.body, request.charset))
                    state = h.getStateObject(values)
                    data = schema.to_python(values, state)
                    formDict = form.getDict()
                    form = updateForm(form, data)
                    # form will be False if there are no changes (cf. updateForm).
                    if form:
                        backupForm(formDict, form.datetimeModified)
                        Session.add(form)
                        Session.commit()
                        updateApplicationSettingsIfFormIsForeignWord(form)
                        if updateHasChangedTheAnalysis(form, formDict):
                            updateFormsContainingThisFormAsMorpheme(form, 'update', formDict)
                        return form
                    else:
                        response.status_int = 400
                        return {'error':
                            u'The update request failed because the submitted data were not new.'}
                except h.JSONDecodeError:
                    response.status_int = 400
                    return h.JSONDecodeErrorResponse
                except Invalid, e:
                    response.status_int = 400
                    return {'errors': e.unpack_errors()}
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no form with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /forms/id: Delete an existing form.  Only the enterer and
        administrators can delete a form.
        """
        form = h.eagerloadForm(Session.query(Form)).get(id)
        if form:
            if session['user'].role == u'administrator' or \
            form.enterer is session['user']:
                formDict = form.getDict()
                backupForm(formDict)
                updateCollectionsReferencingThisForm(form)
                Session.delete(form)
                Session.commit()
                updateApplicationSettingsIfFormIsForeignWord(form)
                updateFormsContainingThisFormAsMorpheme(form, 'delete')
                return form
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no form with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /forms/id: Return a JSON object representation of the form with
        id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """
        form = h.eagerloadForm(Session.query(Form)).get(id)
        if form:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, form, unrestrictedUsers):
                return form
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no form with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /forms/id/edit: Return the data necessary to update an existing
        OLD form, i.e., the form's properties and the necessary additional data,
        i.e., grammaticalities, speakers, etc.

        This action can be thought of as a combination of the 'show' and 'new'
        actions.  The output will be a JSON object of the form

            {form: {...}, data: {...}},

        where output.form is an object containing the form's properties (cf. the
        output of show) and output.data is an object containing the data
        required to add a new form (cf. the output of new).

        GET parameters will affect the value of output.data in the same way as
        for the new action, i.e., no params will result in all the necessary
        output.data being retrieved from the db while specified params will
        result in selective retrieval (see getNewEditFormData for details).
        """
        form = h.eagerloadForm(Session.query(Form)).get(id)
        if form:
            unrestrictedUsers = h.getUnrestrictedUsers()
            if h.userIsAuthorizedToAccessModel(session['user'], form, unrestrictedUsers):
                return {'data': getNewEditFormData(request.GET), 'form': form}
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no form with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """GET /forms/history/id: Return a JSON object representation of the form and its previous versions.

        The id parameter can be either an integer id or a UUID.  If no form and
        no form backups match id, then a 404 is returned.  Otherwise a 200 is
        returned (or a 403 if the restricted keyword is relevant).  See below:

        form                None    None          form       form
        previousVersions    []      [1, 2,...]    []         [1, 2,...]
        response            404     200/403       200/403    200/403
        """
        form, previousVersions = getFormAndPreviousVersions(id)
        if form or previousVersions:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            accessible = h.userIsAuthorizedToAccessModel
            unrestrictedPreviousVersions = [fb for fb in previousVersions
                                    if accessible(user, fb, unrestrictedUsers)]
            formIsRestricted = form and not accessible(user, form, unrestrictedUsers)
            previousVersionsAreRestricted = previousVersions and not \
                unrestrictedPreviousVersions
            if formIsRestricted or previousVersionsAreRestricted :
                response.status_int = 403
                return h.unauthorizedMsg
            else :
                return {'form': form,
                        'previousVersions': unrestrictedPreviousVersions}
        else:
            response.status_int = 404
            return {'error': 'No forms or form backups match %s' % id}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    def remember(self):
        """Store references to the forms passed as input (via id) in the logged
        in user's rememberedForms array.  The input is a JSON object of the form
        {'forms': [id1, id2, ...]}.
        """
        try:
            schema = FormIdsSchema
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            forms = [f for f in data['forms'] if f]
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        else:
            if forms:
                accessible = h.userIsAuthorizedToAccessModel
                unrestrictedUsers = h.getUnrestrictedUsers()
                user = session['user']
                unrestrictedForms = [f for f in forms
                                     if accessible(user, f, unrestrictedUsers)]
                if unrestrictedForms:
                    session['user'].rememberedForms += unrestrictedForms
                    session['user'].datetimeModified = h.now()
                    Session.commit()
                    return [f.id for f in unrestrictedForms]
                else:
                    response.status_int = 403
                    return h.unauthorizedMsg
            else:
                response.status_int = 404
                return {'error': u'No valid form ids were provided.'}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator'])
    def update_morpheme_references(self):
        """Update all of the morpheme references (i.e., the morphemeBreakIDs,
        morphemeGlossIDs and syntacticCategoryString fields) by calling
        updateForm on each form in the database.  Return a list of ids
        corresponding to the forms that were updated.

        Note 1: this functionality should probably be replaced by client-side
        logic that makes multiple requests to PUT /forms/id since the current
        implementation may overtax memory resources when the database is quite
        large.

        Note 2: if this function is to be executed as a scheduled task, we need
        to decide what to do about the backuper attribute.
        
        Note 3: updateFormsContainingThisFormAsMorpheme is effective on create,
        update and delete requests, then the update_morpheme_references
        functionality may be rendered obsolete ...
        """
        return updateMorphemeReferencesOfForms(h.getForms(), h.getMorphemeDelimiters())


def updateApplicationSettingsIfFormIsForeignWord(form):
    """If the input form is a foreign word, attempt to update the attributes in
    app_globals.applicationSettings.
    """

    if h.formIsForeignWord(form):
        try:
            applicationSettings = getattr(app_globals, 'applicationSettings', None)
            applicationSettings.getAttributes()
        except AttributeError:
            app_globals.applicationSettings = h.ApplicationSettings()
        except NameError:
            pass


def getNewEditFormData(GET_params):
    """Return the data necessary to create a new OLD form or update an existing
    one.  The GET_params parameter is the request.GET dictionary-like object
    generated by Pylons.

    If no parameters are provided (i.e., GET_params is empty), then retrieve all
    data (i.e., grammaticalities, speakers, etc.) from the db and return it.

    If parameters are specified, then for each parameter whose value is a
    non-empty string (and is not a valid ISO 8601 datetime), retrieve and
    return the appropriate list of objects.

    If the value of a parameter is a valid ISO 8601 datetime string,
    retrieve and return the appropriate list of objects *only* if the
    datetime param does *not* match the most recent datetimeModified value
    of the relevant data store.  This makes sense because a non-match indicates
    that the requester has out-of-date data.

    """

    # Map param names to the OLD model objects from which they are derived.
    paramName2ModelName = {
        'grammaticalities': 'ApplicationSettings',
        'elicitationMethods': 'ElicitationMethod',
        'tags': 'Tag',
        'syntacticCategories': 'SyntacticCategory',
        'speakers': 'Speaker',
        'users': 'User',
        'sources': 'Source'
    }

    # map_ maps param names to functions that retrieve the appropriate data
    # from the db.
    map_ = {
        'grammaticalities': h.getGrammaticalities,
        'elicitationMethods': h.getMiniDictsGetter('ElicitationMethod'),
        'tags': h.getMiniDictsGetter('Tag'),
        'syntacticCategories': h.getMiniDictsGetter('SyntacticCategory'),
        'speakers': h.getMiniDictsGetter('Speaker'),
        'users': h.getMiniDictsGetter('User'),
        'sources': h.getMiniDictsGetter('Source')
    }

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in map_])

    # There are GET params, so we are selective in what we return.
    if GET_params:
        for key in map_:
            val = GET_params.get(key)
            # Proceed so long as val is not an empty string.
            if val:
                valAsDatetimeObj = h.datetimeString2datetime(val)
                if valAsDatetimeObj:
                    # Value of param is an ISO 8601 datetime string that
                    # does not match the most recent datetimeModified of the
                    # relevant model in the db: therefore we return a list
                    # of objects/dicts.  If the datetimes do match, this
                    # indicates that the requester's own stores are
                    # up-to-date so we return nothing.
                    if valAsDatetimeObj != \
                    h.getMostRecentModificationDatetime(
                    paramName2ModelName[key]):
                        result[key] = map_[key]()
                else:
                    result[key] = map_[key]()

    # There are no GET params, so we get everything from the db and return it.
    else:
        for key in map_:
            result[key] = map_[key]()

    return result


def getFormAndPreviousVersions(id):
    """The id parameter is a string representing either an integer id or a UUID.
    Return the form such that form.id==id or form.UUID==UUID (if there is one)
    as well as all form backups such that formBackup.UUID==id or
    formBackup.form_id==id.
    """

    form = None
    previousVersions = []
    try:
        id = int(id)
        form = h.eagerloadForm(Session.query(Form)).get(id)
        if form:
            previousVersions = h.getFormBackupsByUUID(form.UUID)
        else:
            previousVersions = h.getFormBackupsByFormId(id)
    except ValueError:
        try:
            UUID = unicode(h.UUID(id))
            form = h.getFormByUUID(UUID)
            previousVersions = h.getFormBackupsByUUID(UUID)
        except (AttributeError, ValueError):
            pass    # id is neither an integer nor a UUID
    return (form, previousVersions)


################################################################################
# Backup form
################################################################################

def backupForm(formDict, datetimeModified=None):
    """When a form is updated or deleted, it is first added to the formbackup
    table.  When backing up a form that is being updated, set update to True.
    """

    formBackup = FormBackup()
    formBackup.vivify(formDict, session['user'], datetimeModified)
    Session.add(formBackup)



################################################################################
# Form Create & Update Functions
################################################################################

def createNewForm(data):
    """Create a new Form model object given a data dictionary provided by the
    user (as a JSON object).
    """

    form = Form()
    form.UUID = unicode(uuid4())

    # Unicode Data
    form.transcription = h.toSingleSpace(h.normalize(data['transcription']))
    form.phoneticTranscription = h.toSingleSpace(h.normalize(
                                            data['phoneticTranscription']))
    form.narrowPhoneticTranscription = h.toSingleSpace(h.normalize(
                                        data['narrowPhoneticTranscription']))
    form.morphemeBreak = h.toSingleSpace(h.normalize(data['morphemeBreak']))
    form.morphemeGloss = h.toSingleSpace(h.normalize(data['morphemeGloss']))
    form.comments = h.normalize(data['comments'])
    form.speakerComments = h.normalize(data['speakerComments'])
    form.grammaticality = data['grammaticality']
    form.status = data['status']

    # User-entered date: dateElicited
    form.dateElicited = data['dateElicited']

    # Many-to-One
    form.elicitationMethod = data['elicitationMethod']
    form.syntacticCategory = data['syntacticCategory']
    form.source = data['source']
    form.elicitor = data['elicitor']
    form.verifier = data['verifier']
    form.speaker = data['speaker']

    # One-to-Many Data: translations
    form.translations = data['translations']

    # Many-to-Many Data: tags & files
    form.tags = [t for t in data['tags'] if t]
    form.files = [f for f in data['files'] if f]

    # Restrict the entire form if it is associated to restricted files.
    tags = [f.tags for f in form.files]
    tags = [tag for tagList in tags for tag in tagList]
    restrictedTags = [tag for tag in tags if tag.name == u'restricted']
    if restrictedTags:
        restrictedTag = restrictedTags[0]
        if restrictedTag not in form.tags:
            form.tags.append(restrictedTag)

    # OLD-generated Data
    now = datetime.datetime.utcnow()
    form.datetimeEntered = now
    form.datetimeModified = now
    form.enterer = session['user']

    # Create the morphemeBreakIDs and morphemeGlossIDs attributes.
    # We add the form first to get an ID so that monomorphemic Forms can be
    # self-referential.
    Session.add(form)
    form.morphemeBreakIDs, form.morphemeGlossIDs, form.syntacticCategoryString, form.breakGlossCategory = \
                                                        compileMorphemicAnalysis(form)
    return form

def updateForm(form, data):
    """Update the input Form model object given a data dictionary provided by
    the user (as a JSON object).  If changed is not set to true in the course
    of attribute setting, then False is returned and no update occurs.
    """
    changed = False
    # Unicode Data
    changed = h.setAttr(form, 'transcription',
            h.toSingleSpace(h.normalize(data['transcription'])), changed)
    changed = h.setAttr(form, 'phoneticTranscription',
            h.toSingleSpace(h.normalize(data['phoneticTranscription'])), changed)
    changed = h.setAttr(form, 'narrowPhoneticTranscription',
            h.toSingleSpace(h.normalize(data['narrowPhoneticTranscription'])), changed)
    changed = h.setAttr(form, 'morphemeBreak',
            h.toSingleSpace(h.normalize(data['morphemeBreak'])), changed)
    changed = h.setAttr(form, 'morphemeGloss',
            h.toSingleSpace(h.normalize(data['morphemeGloss'])), changed)
    changed = h.setAttr(form, 'comments', h.normalize(data['comments']), changed)
    changed = h.setAttr(form, 'speakerComments', h.normalize(data['speakerComments']), changed)
    changed = h.setAttr(form, 'grammaticality', data['grammaticality'], changed)
    changed = h.setAttr(form, 'status', data['status'], changed)

    # User-entered date: dateElicited
    changed = h.setAttr(form, 'dateElicited', data['dateElicited'], changed)

    # One-to-Many Data: Translations
    # First check if the user has made any changes to the translations.
    # If there are changes, then delete all translations and replace with new
    #  ones.  (Note: this will result in the deletion of a translation and the
    #  recreation of an identical one with a different index.  There may be a
    #  "better" way of doing this, but this way is simple...
    translationsWeHave = [(t.transcription, t.grammaticality) for t in form.translations]
    translationsToAdd = [(t.transcription, t.grammaticality) for t in data['translations']]
    if set(translationsWeHave) != set(translationsToAdd):
        form.translations = data['translations']
        changed = True

    # Many-to-One Data
    changed = h.setAttr(form, 'elicitationMethod', data['elicitationMethod'], changed)
    changed = h.setAttr(form, 'syntacticCategory', data['syntacticCategory'], changed)
    changed = h.setAttr(form, 'source', data['source'], changed)
    changed = h.setAttr(form, 'elicitor', data['elicitor'], changed)
    changed = h.setAttr(form, 'verifier', data['verifier'], changed)
    changed = h.setAttr(form, 'speaker', data['speaker'], changed)

    # Many-to-Many Data: tags & files
    # Update only if the user has made changes.
    filesToAdd = [f for f in data['files'] if f]
    tagsToAdd = [t for t in data['tags'] if t]

    if set(filesToAdd) != set(form.files):
        form.files = filesToAdd
        changed = True

        # Cause the entire form to be tagged as restricted if any one of its
        # files are so tagged.
        tags = [f.tags for f in form.files]
        tags = [tag for tagList in tags for tag in tagList]
        restrictedTags = [tag for tag in tags if tag.name == u'restricted']
        if restrictedTags:
            restrictedTag = restrictedTags[0]
            if restrictedTag not in tagsToAdd:
                tagsToAdd.append(restrictedTag)

    if set(tagsToAdd) != set(form.tags):
        form.tags = tagsToAdd
        changed = True

    # Create the morphemeBreakIDs and morphemeGlossIDs attributes.
    morphemeBreakIDs, morphemeGlossIDs, syntacticCategoryString, breakGlossCategory = \
                                                        compileMorphemicAnalysis(form)

    changed = h.setAttr(form, 'morphemeBreakIDs', morphemeBreakIDs, changed)
    changed = h.setAttr(form, 'morphemeGlossIDs', morphemeGlossIDs, changed)
    changed = h.setAttr(form, 'syntacticCategoryString', syntacticCategoryString, changed)
    changed = h.setAttr(form, 'breakGlossCategory', breakGlossCategory, changed)

    if changed:
        form.datetimeModified = datetime.datetime.utcnow()
        return form
    return changed


def updateMorphemeReferencesOfForm(form, validDelimiters=None, **kwargs):
    """This function behaves just like updateForm() above except that it doesn't
    take a dict of form data as input; it rather attempts to update the morpheme
    reference data by calling compileMorphemicAnalysis.

    If specified, lexicalItems should be a list of lexical forms with which the
    new morphemic analyses should (exclusively) be constructed.
    """
    changed = False
    morphemeBreakIDs, morphemeGlossIDs, syntacticCategoryString, breakGlossCategory = \
        compileMorphemicAnalysis(form, validDelimiters, **kwargs)
    changed = h.setAttr(form, 'morphemeBreakIDs', morphemeBreakIDs, changed)
    changed = h.setAttr(form, 'morphemeGlossIDs', morphemeGlossIDs, changed)
    changed = h.setAttr(form, 'syntacticCategoryString', syntacticCategoryString, changed)
    changed = h.setAttr(form, 'breakGlossCategory', breakGlossCategory, changed)
    if changed:
        form.datetimeModified = datetime.datetime.utcnow()
        return form
    return changed

def updateMorphemeReferencesOfForms(forms, validDelimiters, **kwargs):
    """Calls updateMorphemeReferencesOfForm for each form in forms, commits any
    changes, backs up the form (if necessary) and returns a list of ids corresponding
    to the updated forms.

    If specified, lexicalItems should be a list of lexical forms with which the
    new morphemic analyses of all forms should (exclusively) be constructed.
    """
    updatedFormIds = []
    for form in forms:
        formDict = form.getDict()
        form = updateMorphemeReferencesOfForm(form, validDelimiters, **kwargs)
        # form will be False if there are no changes.
        if form:
            backupForm(formDict, form.datetimeModified)
            Session.add(form)
            Session.commit()
            updatedFormIds.append(form.id)
    return updatedFormIds


def compileMorphemicAnalysis(form, morphemeDelimiters=None, **kwargs):
    """Wrapper arround _compileMorphemicAnalysis that softens errors :)"""
    try:
        return _compileMorphemicAnalysis(form, morphemeDelimiters, **kwargs)
    except Exception, e:
        log.debug('compileMorphemicAnalysis raised an error (%s) on "%s"/"%s".' % (
            e, form.morphemeBreak, form.morphemeGloss))
        return None, None, None, None

def _compileMorphemicAnalysis(form, morphemeDelimiters=None, **kwargs):
    """This function generates values for the morphemeBreakIDs,
    morphemeGlossIDs, syntacticCategoryString and breakGlossCategory attributes
    of the input form.  It takes the morphemes and morpheme glosses of the Form
    and looks for matches in other (lexical) Forms.

    For each morpheme (i.e., each (phonemic_form, gloss) tuple) detected in the
    target form, the database is searched for forms whose morpheme break field
    matches the phonemic form and whose morpheme gloss matches the gloss.  If
    such a perfect match is not found, the database is searched for forms
    matching just the phonemic form or just the gloss.

    Matches are stored as triples of the form (id, mb/gl, sc).  For example,
    consider a form with morphemeBreak value u'chien-s' and morphemeGloss value
    u'dog-PL' and assume the lexical entries 'chien/dog/N/33', 's/PL/Agr/103' and
    's/PL/Num/111' (where, for /a/b/c/d, a is the morpheme break, b is the
    morpheme gloss, c is the syntactic category and d is the database id.
    Running compileMorphemicAnalysis on the target form will the following
    quadruple q

    (
        json.dumps([[[[33, u'dog', u'N']], [[111, u'PL', u'Num'], [103, u'PL', u'Agr']]]]),
        json.dumps([[[[33, u'chien', u'N']], [[111, u's', u'Num'], [103, u's', u'Agr']]]]),
        u'N-Num',
        u'chien|dog|N-s|PL|Num'
    ),

    where q[0] is morphemeBreakIDs, q[1] is morphemeGlossIDs, q[2] is
    syntacticCategoryString and q[3] is breakGlossCategory.

    If kwargs contains a 'lexicalItems' or a 'deletedLexicalItems' key, then
    compileMorphemicAnalysis will *update* (i.e., not re-create) the 4 relevant
    values of the form using only the items in the kwargs['lexicalItems'] or
    kwargs['deletedLexicalItems'] lists.  This facilitates lexical change
    percolation without massively redundant database requests.
    """

    def join(bgc, morphemeDelimiters, bgcDelimiter):
        """This function joins the bgc ("break-gloss-category") triple using the
        supplied bgc delimiter.  If the bgc is a list of morpheme/word
        delimiters, then the first such delimiter is returned, e.g.,
        join([('le', 'the', 'Det')], ['-', '=', ' '], '|') yields u'le|the|Det',
        join([('-', '-', '-')], ['-', '=', ' '], '|') yields u'-' and
        join([('=', '-', '=')], ['-', '=', ' '], '|') yields u'='.
        """

        if bgc[0] in morphemeDelimiters and bgc[1] in morphemeDelimiters and \
        bgc[2] in morphemeDelimiters:
            return bgc[0]
        return bgcDelimiter.join(bgc)

    def morphemicAnalysisIsConsistent(**kwargs):
        """Return True only if the morphemeBreak and morphemeGloss fields are not
        empty, there are equal numbers of morpheme break and morpheme gloss "words"
        and each morpheme break word has the same number of morphemes as its
        morpheme gloss counterpart.
        """
        return kwargs['morphemeBreak'] != u'' and \
        kwargs['morphemeGloss'] != u'' and \
        len(kwargs['mbWords']) == len(kwargs['mgWords']) and \
        [len(re.split(kwargs['morphemeSplitter'], mbw)) for mbw in kwargs['mbWords']] == \
        [len(re.split(kwargs['morphemeSplitter'], mgw)) for mgw in kwargs['mgWords']]

    def getCategoryFromPartialMatch(morphemeMatches, glossMatches):
        """This function is used to generate a syntactic category for a morpheme
        given a partial match.  First it looks through all of the morpheme matches,
        then all of the gloss matches and returns u'?' as a default.  Somewhat arbitrary...
        """
        return filter(None,
            [getattr(m.syntacticCategory, 'name', None) for m in morphemeMatches] +
            [getattr(g.syntacticCategory, 'name', None) for g in glossMatches] + [u'?'])[0]

    def getBreakGlossCategory(morphemeDelimiters, morphemeBreak, morphemeGloss,
                              syntacticCategoryString, bgcDelimiter):
        """Return the breakGlossCategory value, e.g. 'le|the|Det-s|PL|Num chien|dog|N-s|PL|Num'."""
        try:
            delimiters = [u' '] + morphemeDelimiters
            splitter = u'([%s])' % ''.join([h.escREMetaChars(d) for d in delimiters])
            mbSplit = filter(None, re.split(splitter, morphemeBreak))
            mgSplit = filter(None, re.split(splitter, morphemeGloss))
            scSplit = filter(None, re.split(splitter, syntacticCategoryString))
            breakGlossCategory = zip(mbSplit, mgSplit, scSplit)
            return u''.join([join(bgc, delimiters, bgcDelimiter) for bgc in breakGlossCategory])
        except TypeError:
            return None

    def getFakeForm(quadruple):
        """Return an object that behaves like a form insofar as it has 'id',
        'morphemeBreak', 'morphemeGloss' and 'syntacticCategory' values.
        """
        class FakeForm(object):
            pass
        class FakeSyntacticCategory(object):
            pass
        fakeForm = FakeForm()
        fakeSyntacticCategory = FakeSyntacticCategory()
        fakeSyntacticCategory.name = quadruple[3]
        fakeForm.id = quadruple[0]
        fakeForm.morphemeBreak = quadruple[1]
        fakeForm.morphemeGloss = quadruple[2]
        fakeForm.syntacticCategory = fakeSyntacticCategory
        return fakeForm

    def getPerfectMatches(form, wordIndex, morphemeIndex, morpheme, gloss, matchesFound,
                          lexicalItems, deletedLexicalItems):
        """Return a list of (lexical) forms in the database such that, for each
        lf, lf.morphemeBreak = morpheme AND lf.morphemeGloss = gloss.

        If one of lexicalItems or deletedLexicalItems is truthy, then the result returned
        will be generated using only those lists AND the existing references in
        the morphemeBreak and morphemeGloss attributes.  This facilitates lexical
        change percolation without massively redundant database requests.  Note
        that the presence of a non-empty lexicalItems/deletedLexicalItems implies
        that the supplied forms represent the only (relevant) changes to the database.

        One complication arises from the fact that perfect matches mask partial ones.
        If getPerfectMatches results in all originally existing perfect matches being
        removed, then it is possible that the db contains partial matches that are not
        listed in lexicalItems.  Therefore, we need to tell getPartialMatches that it
        must query the database *only* when the morpheme in question is encountered.
        We do this by returning an ordered pair (tuple) containing this morpheme.

        Note that this function always returns an ordered pair (tuple), where the
        second element is the matchesFound dict which stores results already found.
        In the normal case, the first element is the list of matches found for the
        input m/g.  When we need to force getPartialMatches to query, the first element
        is the (m, g) tuple.
        """
        if (morpheme, gloss) in matchesFound:
            return matchesFound[(morpheme, gloss)], matchesFound
        if lexicalItems or deletedLexicalItems:
            extantMorphemeBreakIDs = json.loads(form.morphemeBreakIDs)
            extantMorphemeGlossIDs = json.loads(form.morphemeGlossIDs)
            # Extract extant perfect matches as quadruples: (id, mb, mg, sc)
            extantPerfectMatchesOriginally = [(x[0][0], x[1][1], x[0][1], x[0][2])
                for x in zip(extantMorphemeBreakIDs[wordIndex][morphemeIndex],
                             extantMorphemeGlossIDs[wordIndex][morphemeIndex])
                if x[0][0] == x[1][0]]
            # Make extant matches look like form objects and remove those that
            # may have been deleted or updated
            extantPerfectMatches = [getFakeForm(m) for m in extantPerfectMatchesOriginally
                if m[0] not in [f.id for f in lexicalItems + deletedLexicalItems]]
            perfectMatchesInLexicalItems = [f for f in lexicalItems
                if f.morphemeBreak == morpheme and f.morphemeGloss == gloss]
            perfectMatchesNow = sorted(extantPerfectMatches + perfectMatchesInLexicalItems,
                                       key=lambda f: f.id)
            # If perfect matches have been emptied by us, we return a tuple so that
            # getPartialMatches knows to query the database for this morpheme only
            if perfectMatchesNow == [] and extantPerfectMatchesOriginally != []:
                return (morpheme, gloss), matchesFound
            result = perfectMatchesNow
        else:
            result = Session.query(Form)\
                .filter(Form.morphemeBreak==morpheme)\
                .filter(Form.morphemeGloss==gloss).order_by(asc(Form.id)).all()
        matchesFound[(morpheme, gloss)] = result
        return result, matchesFound

    def getPartialMatches(form, wordIndex, morphemeIndex, matchesFound, **kwargs):
        """This function behaves similarly to getPerfectMatches above except that
        it returns partial matches.  It assumes that kwargs['morpheme'] xor
        kwargs['gloss'] is present and uses that information to return the
        correct type of matches.  If 'lexicalItems' or 'deletedLexicalItems' is
        in kwargs, then that list of forms will be used to build the list of
        partial matches and the database will not be queried, cf.
        getPerfectMatches above.

        The only case where the db will be queried (when lexicalItems or
        deletedLexicalItems) are supplied is when forceQuery is (morpheme, gloss).
        This indicates that getPerfectMatches is telling us that the supplied
        lexical info resulted in perfectMatches being emptied and that therefore
        we should search the db for potentially masked partial matches.

        Note that this function always returns an ordered pair (tuple), where the
        first element is the list of matches found for this particular m/g and the
        second is the (potentially updated) matchesFound dict which stores results
        already found for all the morphemes in the form being analyzed.
        """
        lexicalItems = kwargs.get('lexicalItems')
        deletedLexicalItems = kwargs.get('deletedLexicalItems')
        forceQuery = kwargs.get('forceQuery')   # The output of getPerfectMatches: [] or (morpheme, gloss)
        morpheme = kwargs.get('morpheme')
        gloss = kwargs.get('gloss')
        attribute = morpheme and u'morphemeBreak' or u'morphemeGloss'
        value = morpheme or gloss
        if (morpheme, gloss) in matchesFound:
            return matchesFound[(morpheme, gloss)], matchesFound
        if lexicalItems or deletedLexicalItems:
            if value in forceQuery:
                result = Session.query(Form)\
                        .filter(getattr(Form, attribute)==value).order_by(asc(Form.id)).all()
            else:
                extantAnalyses = json.loads(getattr(form, attribute + 'IDs'))[wordIndex][morphemeIndex]
                # Extract extant partial matches as quadruples of the form (id, mb, mg, sc)
                # where one of mb or mg will be None.
                extantPartialMatches = [(x[0], None, x[1], x[2]) if morpheme else
                                    (x[0], x[1], None, x[2]) for x in extantAnalyses]
                # Make extant matches look like form objects and remove those that
                # may have been deleted or updated
                extantPartialMatches = [getFakeForm(m) for m in extantPartialMatches
                    if m[0] not in [f.id for f in lexicalItems + deletedLexicalItems]]
                partialMatchesInLexicalItems = [f for f in lexicalItems
                                                if getattr(f, attribute) == value]
                result = sorted(extantPartialMatches + partialMatchesInLexicalItems,
                              key=lambda f: f.id)
        else:
            result = Session.query(Form).filter(getattr(Form, attribute)==value).order_by(asc(Form.id)).all()
        matchesFound[(morpheme, gloss)] = result
        return result, matchesFound

    bgcDelimiter = kwargs.get('bgcDelimiter', u'|')     # The default delimiter for the breakGlossCategory field
    lexicalItems = kwargs.get('lexicalItems', [])
    deletedLexicalItems = kwargs.get('deletedLexicalItems', [])
    morphemeBreakIDs = []
    morphemeGlossIDs = []
    syntacticCategoryString = []
    morphemeDelimiters = morphemeDelimiters or h.getMorphemeDelimiters()
    morphemeSplitter = morphemeDelimiters and u'[%s]' % ''.join(
                        [h.escREMetaChars(d) for d in morphemeDelimiters]) or u''
    morphemeBreak = form.morphemeBreak
    morphemeGloss = form.morphemeGloss
    mbWords = morphemeBreak.split()     # e.g., u'le-s chien-s'
    mgWords = morphemeGloss.split()     # e.g., u'the-PL dog-PL'
    scWords = morphemeBreak.split()[:]  # e.g., u'le-s chien-s' (placeholder)

    if morphemicAnalysisIsConsistent(morphemeDelimiters=morphemeDelimiters,
        morphemeBreak=morphemeBreak, morphemeGloss=morphemeGloss, mbWords=mbWords,
        mgWords=mgWords, morphemeSplitter=morphemeSplitter):
        matchesFound = {}   # temporary store -- eliminates redundant queries & processing -- updated as a byproduct of getPerfectMatches and getPartialMatches
        for i in range(len(mbWords)):
            mbWordAnalysis = []
            mgWordAnalysis = []
            mbWord = mbWords[i]     # e.g., u'chien-s'
            mgWord = mgWords[i]     # e.g., u'dog-PL'
            scWord = scWords[i]     # e.g., u'chien-s'
            morphemeAndDelimiterSplitter = '(%s)' % morphemeSplitter    # splits on delimiters while retaining them
            mbWordMorphemesList = re.split(morphemeAndDelimiterSplitter, mbWord)[::2]   # e.g., ['chien', 's']
            mgWordMorphemesList = re.split(morphemeAndDelimiterSplitter, mgWord)[::2]   # e.g., ['dog', 'PL']
            scWordAnalysis = re.split(morphemeAndDelimiterSplitter, scWord)    # e.g., ['chien', '-', 's']
            for j in range(len(mbWordMorphemesList)):
                morpheme = mbWordMorphemesList[j]
                gloss = mgWordMorphemesList[j]
                perfectMatches, matchesFound = getPerfectMatches(form, i, j, morpheme, gloss,
                                            matchesFound, lexicalItems, deletedLexicalItems)
                if perfectMatches and type(perfectMatches) is list:
                    mbWordAnalysis.append([(f.id, f.morphemeGloss,
                        getattr(f.syntacticCategory, 'name', None)) for f in perfectMatches])
                    mgWordAnalysis.append([(f.id, f.morphemeBreak,
                        getattr(f.syntacticCategory, 'name', None)) for f in perfectMatches])
                    scWordAnalysis[j * 2] = getattr(perfectMatches[0].syntacticCategory, 'name', u'?')
                else:
                    morphemeMatches, matchesFound = getPartialMatches(form, i, j, matchesFound, morpheme=morpheme,
                                        forceQuery=perfectMatches, lexicalItems=lexicalItems,
                                        deletedLexicalItems=deletedLexicalItems)
                    if morphemeMatches:
                        mbWordAnalysis.append([(f.id, f.morphemeGloss,
                            getattr(f.syntacticCategory, 'name', None)) for f in morphemeMatches])
                    else:
                        mbWordAnalysis.append([])
                    glossMatches, matchesFound = getPartialMatches(form, i, j, matchesFound, gloss=gloss,
                                        forceQuery=perfectMatches, lexicalItems=lexicalItems,
                                        deletedLexicalItems=deletedLexicalItems)
                    if glossMatches:
                        mgWordAnalysis.append([(f.id, f.morphemeBreak,
                            getattr(f.syntacticCategory, 'name', None)) for f in glossMatches])
                    else:
                        mgWordAnalysis.append([])
                    scWordAnalysis[j * 2] = getCategoryFromPartialMatch(morphemeMatches, glossMatches)
            morphemeBreakIDs.append(mbWordAnalysis)
            morphemeGlossIDs.append(mgWordAnalysis)
            syntacticCategoryString.append(''.join(scWordAnalysis))
        syntacticCategoryString = u' '.join(syntacticCategoryString)
        breakGlossCategory = getBreakGlossCategory(morphemeDelimiters, morphemeBreak,
                                                   morphemeGloss, syntacticCategoryString, bgcDelimiter)
    else:
        morphemeBreakIDs = morphemeGlossIDs = syntacticCategoryString = breakGlossCategory = None
    return unicode(json.dumps(morphemeBreakIDs)), unicode(json.dumps(morphemeGlossIDs)), \
           syntacticCategoryString, breakGlossCategory



################################################################################
# Form -> Morpheme updating functionality
################################################################################

def updateFormsContainingThisFormAsMorpheme(form, change='create', previousVersion=None):
    """This function updates the morphemeBreadIDs, morphemeGlossIDs,
    syntacticCategoryString, and breakGlossCategory attributes of each form that
    contains the input form, i.e., each form whose morphemeBreak line contains
    the input form's morphemeBreak line as a morpheme or whose morphemeGloss line
    contains the input form's morphemeGloss line as a gloss.  Note that if the
    input form is not lexical (i.e., if it contains the space character or a
    morpheme delimiter), then no changes will be made.

    This function is called in each of the create, update and delete actions whenever
    they succeed.  The change parameter signifies the type of action.  The
    previousVersion parameter contains a dict representation of an updated form's
    previous state.  This function is also the one called in the syntacticcategories
    controller when a lexical category is deleted or has its name changed.
    """

    if h.isLexical(form):
        # Here we construct the query to get all forms that may have been affected
        # by the change to the lexical item (i.e., form).
        morphemeDelimiters = h.getMorphemeDelimiters()
        escapedMorphemeDelimiters = [h.escREMetaChars(d) for d in morphemeDelimiters]
        startPatt = '(%s)' % '|'.join(escapedMorphemeDelimiters + [u' ', '^'])
        endPatt = '(%s)' % '|'.join(escapedMorphemeDelimiters + [u' ', '$'])
        morphemePatt = '%s%s%s' % (startPatt, form.morphemeBreak, endPatt)
        glossPatt = '%s%s%s' % (startPatt, form.morphemeGloss, endPatt)
        disjunctiveConditions = [Form.morphemeBreak.op('regexp')(morphemePatt),
                                 Form.morphemeGloss.op('regexp')(glossPatt)]
        matchesQuery = Session.query(Form).options(subqueryload(Form.syntacticCategory))

        # Updates entail a wider range of possibly affected forms
        if previousVersion and h.isLexical(previousVersion):
            if previousVersion['morphemeBreak'] != form.morphemeBreak:
                morphemePattPV = '%s%s%s' % (startPatt, previousVersion['morphemeBreak'], endPatt)
                disjunctiveConditions.append(Form.morphemeBreak.op('regexp')(morphemePattPV))
            if previousVersion['morphemeGloss'] != form.morphemeGloss:
                glossPattPV = '%s%s%s' % (startPatt, previousVersion['morphemeGloss'], endPatt)
                disjunctiveConditions.append(Form.morphemeGloss.op('regexp')(glossPattPV))

        matchesQuery = matchesQuery.filter(or_(*disjunctiveConditions))
        #matches = [f for f in matchesQuery.all() if f.id != form.id]
        matches = matchesQuery.all()

        if change == 'delete':
            updatedFormIds = updateMorphemeReferencesOfForms(matches,
                                morphemeDelimiters, deletedLexicalItems=[form])
        else:
            updatedFormIds = updateMorphemeReferencesOfForms(matches,
                                morphemeDelimiters, lexicalItems=[form])

def updateHasChangedTheAnalysis(form, formDict):
    """Return True if the update from formDict to form has changed the analysis
    of the form, i.e., if the morphemeBreak, morphemeGloss or syncat name have changed.
    """
    try:
        oldSyntacticCategoryName = formDict['syntacticCategory'].get('name')
    except AttributeError:
        oldSyntacticCategoryName = None
    return form.morphemeBreak != formDict['morphemeBreak'] or \
           form.morphemeGloss != formDict['morphemeGloss'] or \
           form.breakGlossCategory != formDict['breakGlossCategory'] or \
           getattr(form.syntacticCategory, 'name', None) != oldSyntacticCategoryName


def updateCollectionsReferencingThisForm(form):
    """When a form is deleted, it is necessary to update all collections whose
    ``contents`` value references the deleted form.  The update removes the
    reference, and recomputes the ``contentsUnpacked``, ``html`` and ``forms``
    attributes of the affected collection and causes all of these changes to
    percolate through the collection-collection reference chain.

    Note that getting the collections that reference this form by searching for
    collections whose ``forms`` attribute references this form is not quite the
    correct way to do this because many of these collections will not *directly*
    reference this form -- in short, this will result in redundant updates and
    backups.
    """
    pattern = unicode(h.formReferencePattern.pattern.replace('[0-9]+', str(form.id)))
    collectionsReferencingThisForm = Session.query(Collection).\
        filter(Collection.contents.op('regexp')(pattern)).all()
    for collection in collectionsReferencingThisForm:
        updateCollectionByDeletionOfReferencedForm(collection, form)
