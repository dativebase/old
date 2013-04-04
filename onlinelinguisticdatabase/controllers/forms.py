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

"""Contains the :class:`FormsController` and its auxiliary functions.

.. module:: forms
   :synopsis: Contains the forms controller and its auxiliary functions.

"""

import logging
import re
import simplejson as json
from uuid import uuid4
from pylons import request, response, session, app_globals, config
from formencode.validators import Invalid
from sqlalchemy.sql import asc, or_
from sqlalchemy.orm import subqueryload
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import FormSchema, FormIdsSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Form, FormBackup, Collection
from onlinelinguisticdatabase.controllers.oldcollections import updateCollectionByDeletionOfReferencedForm

log = logging.getLogger(__name__)

class FormsController(BaseController):
    """Generate responses to requests on form resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder(config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of form resources matching the input JSON query.

        :URL: ``SEARCH /forms`` (or ``POST /forms/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "orderBy": [ ... ]},
                 "paginator": { ... }}

            where the ``orderBy`` and ``paginator`` attributes are optional.

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
        """Return the data necessary to search the form resources.

        :URL: ``GET /forms/new_search``
        :returns: ``{"searchParameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all form resources.

        :URL: ``GET /forms`` with optional query string parameters for ordering
            and pagination.
        :returns: a list of all form resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
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
        """Create a new form resource and return it.

        :URL: ``POST /forms``
        :request body: JSON object representing the form to create.
        :returns: the newly created form.

        """
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
        """Return the data necessary to create a new form.

        :URL: ``GET /forms/new`` with optional query string parameters 
        :returns: A dictionary of lists of resources

        .. note::
        
           See :func:`getNewEditFormData` to understand how the query string
           parameters can affect the contents of the lists in the returned
           dictionary.

        """
        return getNewEditFormData(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a form and return it.
        
        :URL: ``PUT /forms/id``
        :Request body: JSON object representing the form with updated attribute values.
        :param str id: the ``id`` value of the form to be updated.
        :returns: the updated form model.

        """
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
                        backupForm(formDict)
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
        """Delete an existing form and return it.

        :URL: ``DELETE /forms/id``
        :param str id: the ``id`` value of the form to be deleted.
        :returns: the deleted form model.

        .. note::

           Only administrators and a form's enterer can delete it.

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
        """Return a form.
        
        :URL: ``GET /forms/id``
        :param str id: the ``id`` value of the form to be returned.
        :returns: a form model object.

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
        """Return a form and the data needed to update it.

        :URL: ``GET /forms/edit`` with optional query string parameters 
        :param str id: the ``id`` value of the form that will be updated.
        :returns: a dictionary of the form::

                {"form": {...}, "data": {...}}

            where the value of the ``form`` key is a dictionary representation
            of the form and the value of the ``data`` key is a dictionary
            containing the objects necessary to update a form, viz. the return
            value of :func:`FormsController.new`

        .. note::
        
           This action can be thought of as a combination of
           :func:`FormsController.show` and :func:`FormsController.new`.  See
           :func:`getNewEditFormData` to understand how the query string
           parameters can affect the contents of the lists in the ``data``
           dictionary.

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
        """Return the form with ``form.id==id`` and its previous versions.

        :URL: ``GET /forms/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            form whose history is requested.
        :returns: A dictionary of the form::

                {"form": { ... }, "previousVersions": [ ... ]}

            where the value of the ``form`` key is the form whose history is
            requested and the value of the ``previousVersions`` key is a list of
            dictionaries representing previous versions of the form.

        """
        form, previousVersions = h.getModelAndPreviousVersions('Form', id)
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
        """Cause the logged in user to remember the forms referenced in the request body.
        
        :URL: ``POST /forms/remember``
        :request body: A JSON object of the form ``{"forms": [ ... ]}`` where
            the value of the ``forms`` attribute is the array of form ``id``
            values representing the forms that are to be remembered.
        :returns: A list of form ``id`` values corresponding to the forms that
            were remembered.

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
        """Update the morphological analysis-related attributes of all forms.

        That is, update the values of the ``morphemeBreakIDs``,
        ``morphemeGlossIDs``, ``syntacticCategoryString`` and
        ``breakGlossCategory`` attributes of every form in the database.

        :URL: ``PUT /forms/update_morpheme_references``
        :returns: a list of ids corresponding to the forms where the update
            caused a change in the values of the target attributes.

        .. warning::
        
           It should not be necessary to request the regeneration of morpheme
           references via this action since this should already be accomplished
           automatically by the calls to
           ``updateFormsContainingThisFormAsMorpheme`` on all successful
           update, create and delete requests on form resources.  This action
           is, therefore, deprecated (read: use it with caution) and may be
           removed in future versions of the OLD.

        """
        return updateMorphemeReferencesOfForms(h.getForms(), h.getMorphemeDelimiters())


def updateApplicationSettingsIfFormIsForeignWord(form):
    """Update the transcription validation functionality of the active application settings if the input form is a foreign word.

    :param form: a form model object
    :returns: ``None``

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
    """Return the data necessary to create a new OLD form or update an existing one.
    
    :param GET_params: the ``request.GET`` dictionary-like object generated by
        Pylons which contains the query string parameters of the request.
    :returns: A dictionary whose values are lists of objects needed to create or
        update forms.

    If ``GET_params`` has no keys, then return all data, i.e., grammaticalities,
    speakers, etc.  If ``GET_params`` does have keys, then for each key whose
    value is a non-empty string (and not a valid ISO 8601 datetime) add the
    appropriate list of objects to the return dictionary.  If the value of a key
    is a valid ISO 8601 datetime string, add the corresponding list of objects
    *only* if the datetime does *not* match the most recent ``datetimeModified``
    value of the resource.  That is, a non-matching datetime indicates that the
    requester has out-of-date data.

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


################################################################################
# Backup form
################################################################################

def backupForm(formDict):
    """Backup a form.

    :param dict formDict: a representation of a form model.
    :returns: ``None``

    """
    formBackup = FormBackup()
    formBackup.vivify(formDict)
    Session.add(formBackup)


################################################################################
# Form Create & Update Functions
################################################################################

def createNewForm(data):
    """Create a new form.

    :param dict data: the form to be created.
    :returns: an SQLAlchemy model object representing the form.

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
    form.syntax = h.normalize(data['syntax'])
    form.semantics = h.normalize(data['semantics'])
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
    form.datetimeEntered = form.datetimeModified = h.now()
    form.enterer = form.modifier = session['user']

    # Create the morphemeBreakIDs and morphemeGlossIDs attributes.
    # We add the form first to get an ID so that monomorphemic Forms can be
    # self-referential.
    Session.add(form)
    form.morphemeBreakIDs, form.morphemeGlossIDs, form.syntacticCategoryString, form.breakGlossCategory = \
                                                        compileMorphemicAnalysis(form)
    return form

def updateForm(form, data):
    """Update a form model.

    :param form: the form model to be updated.
    :param dict data: representation of the updated form.
    :returns: the updated form model or, if ``changed`` has not been set to
        ``True``, then ``False``.

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
    changed = h.setAttr(form, 'syntax', h.normalize(data['syntax']), changed)
    changed = h.setAttr(form, 'semantics', h.normalize(data['semantics']), changed)
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
        form.datetimeModified = h.now()
        form.modifier = session['user']
        return form
    return changed


def updateMorphemeReferencesOfForm(form, validDelimiters=None, **kwargs):
    """Update the morphological analysis-related attributes of a form model.

    Attempt to update the values of the ``morphemeBreakIDs``,
    ``morphemeGlossIDs``, ``syntacticCategoryString`` and ``breakGlossCategory``
    attributes of a form using only the lexical items specified in the list
    ``kwargs['lexicalItems']`` or the list ``kwargs['deletedLexicalItems']``.

    :param form: the form model to be updated.
    :param list validDelimiters: morpheme delimiters as strings.
    :param list kwargs['lexicalItems']: a list of form models.
    :param list kwargs['deletedLexicalItems']: a list of form models.
    :returns: the form if updated; else ``False``.

    """
    changed = False
    morphemeBreakIDs, morphemeGlossIDs, syntacticCategoryString, breakGlossCategory = \
        compileMorphemicAnalysis(form, validDelimiters, **kwargs)
    changed = h.setAttr(form, 'morphemeBreakIDs', morphemeBreakIDs, changed)
    changed = h.setAttr(form, 'morphemeGlossIDs', morphemeGlossIDs, changed)
    changed = h.setAttr(form, 'syntacticCategoryString', syntacticCategoryString, changed)
    changed = h.setAttr(form, 'breakGlossCategory', breakGlossCategory, changed)
    if changed:
        form.datetimeModified = h.now()
        form.modifier = session['user']
        return form
    return changed

def updateMorphemeReferencesOfForms(forms, validDelimiters, **kwargs):
    """Update the morphological analysis-related attributes of a list of form models.

    Attempt to update the values of the ``morphemeBreakIDs``,
    ``morphemeGlossIDs``, ``syntacticCategoryString`` and ``breakGlossCategory``
    attributes of all forms in ``forms`` using only the lexical items specified
    in the list ``kwargs['lexicalItems']`` or ``kwargs['deletedLexicalItems']``.
    Whenever an update occurs, backup the form and commit the changes.

    :param list forms: the form models to be updated.
    :param list validDelimiters: morpheme delimiters as strings.
    :param list kwargs['lexicalItems']: a list of form models.
    :param list kwargs['deletedLexicalItems']: a list of form models.
    :returns: a list of form ``id`` values corresponding to the forms that have
        been updated.

    """
    updatedFormIds = []
    for form in forms:
        formDict = form.getDict()
        form = updateMorphemeReferencesOfForm(form, validDelimiters, **kwargs)
        # form will be False if there are no changes.
        if form:
            backupForm(formDict)
            Session.add(form)
            Session.commit()
            updatedFormIds.append(form.id)
    return updatedFormIds


def compileMorphemicAnalysis(form, morphemeDelimiters=None, **kwargs):
    """An error-handling wrapper arround :func:`compileMorphemicAnalysis_`.

    Catch any error, log it and return a default 4-tuple.

    :param form: the form model for which the morphological values are to be generated.
    :param list validDelimiters: morpheme delimiters as strings.
    :param dict kwargs: arguments that can affect the degree to which the database is queried.
    :returns: the output of :func:`compileMorphemicAnalysis_` or, if an error
        occurs, a 4-tuple of ``None`` objects.

    """
    try:
        return compileMorphemicAnalysis_(form, morphemeDelimiters, **kwargs)
    except Exception, e:
        log.debug('compileMorphemicAnalysis raised an error (%s) on "%s"/"%s".' % (
            e, form.morphemeBreak, form.morphemeGloss))
        return None, None, None, None

def compileMorphemicAnalysis_(form, morphemeDelimiters=None, **kwargs):
    """Generate values fo the morphological analysis-related attributes of a form model.

    :param form: the form model for which the morphological values are to be generated.
    :param list validDelimiters: morpheme delimiters as strings.
    :param dict kwargs: arguments that can affect the degree to which the database is queried.
    :returns: a 4-tuple containing the generated values or all four ``None``
        objects if no values can be generated.

    Generate values for the ``morphemeBreakIDs``, ``morphemeGlossIDs``,
    ``syntacticCategoryString`` and ``breakGlossCategory`` attributes of the
    input form.

    For each morpheme detected in the ``form``, search the database for forms
    whose ``morphemeBreak`` value matches the morpheme's phonemic form and whose
    ``morphemeGloss`` value matches the morpheme's gloss.  If a perfect match is
    not found, searc the database for forms matching just the phonemic form or
    just the gloss.

    Matching forms are represented as triples where the first element is the
    ``id`` value of the match, the second is its ``morphemeBreak`` or
    ``morphemeGloss`` value and the third is its ``syntacticCategory.name``
    value.  To illustrate, consider a form with ``morphemeBreak`` value
    u'chien-s' and ``morphemeGloss`` value u'dog-PL' and assume the lexical
    entries 'chien/dog/N/33', 's/PL/Agr/103' and 's/PL/Num/111' (where, for
    */a/b/c/d*, *a* is the ``morphemeBreak`` value, *b* is the ``morphemeGloss``
    value, *c* is the ``syntacticCategory.name`` value and *d* is the ``id``
    value.  Running :func:`compileMorphemicAnalysis` on the target form returns
    the following 4-tuple ``q``::

        (
            json.dumps([[[[33, u'dog', u'N']], [[111, u'PL', u'Num'], [103, u'PL', u'Agr']]]]),
            json.dumps([[[[33, u'chien', u'N']], [[111, u's', u'Num'], [103, u's', u'Agr']]]]),
            u'N-Num',
            u'chien|dog|N-s|PL|Num'
        )

    where ``q[0]`` is the ``morphemeBreakIDs`` value, ``q[1]`` is the
    ``morphemeGlossIDs`` value, ``q[2]`` is ``syntacticCategoryString`` value
    and ``q[3]`` is ``breakGlossCategory`` value.

    If ``kwargs`` contains a 'lexicalItems' or a 'deletedLexicalItems' key, then
    :func:`compileMorphemicAnalysis` will *update* (i.e., not re-create) the 4
    relevant values of the form using only the items in
    ``kwargs['lexicalItems']`` or ``kwargs['deletedLexicalItems']``.  This
    facilitates lexical change percolation without massively redundant database
    queries.

    """

    def join(bgc, morphemeDelimiters, bgcDelimiter):
        """Convert a break-gloss-category tuple into a delimited string.
        
        Join the break-gloss-category 3-tuple ``bgc`` using the delimiter
        string.  If ``bgc`` contains only morpheme/word delimiters, then the
        first such delimiter is returned::

        :param list bgc: the morpheme as phonemic form, gloss and category.
        :param list morphemeDelimiters: morpheme delimiters as strings.
        :param str bgcDelimiter: delimiter used to join the elements of the morpheme.
        :returns: a string representation of the morpheme.

            >>> join([u'le', u'the', u'Det'], [u'-', u'=', u' '], u'|')
            u'le|the|Det'

            >>> join([u'-', u'-', u'-'], [u'-', u'=', u' '], u'|')
            u'-'

            >>> join([u'=', u'-', u'='], [u'-', u'=', u' '], u'|')
            u'='

        """

        if bgc[0] in morphemeDelimiters and bgc[1] in morphemeDelimiters and \
        bgc[2] in morphemeDelimiters:
            return bgc[0]
        return bgcDelimiter.join(bgc)

    def morphemicAnalysisIsConsistent(**kwargs):
        """Determine whether a morphemic analysis is consistent.
        
        :param dict kwargs: contains the morphological data in various pre-processed states.
        :returns: ``True`` if the morphemic analysis is consistent; ``False`` otherwise.

        "Consistent" means that the ``morphemeBreak`` and ``morphemeGloss``
        values of ``kargs`` are not empty, there are equal numbers of morpheme
        break and morpheme gloss "words" and each morpheme break word has the
        same number of morphemes as its morpheme gloss counterpart.

        """
        return kwargs['morphemeBreak'] != u'' and \
        kwargs['morphemeGloss'] != u'' and \
        len(kwargs['mbWords']) == len(kwargs['mgWords']) and \
        [len(re.split(kwargs['morphemeSplitter'], mbw)) for mbw in kwargs['mbWords']] == \
        [len(re.split(kwargs['morphemeSplitter'], mgw)) for mgw in kwargs['mgWords']]

    def getCategoryFromPartialMatch(morphemeMatches, glossMatches):
        """Return a syntactic category name for a partially matched morpheme.

        :param list morphemeMatches: forms matching the morpheme's transcription.
        :param list glossMatches: forms matching the morpheme's gloss.
        :returns: the category name of the first morpheme match, else that of
            the first gloss match, else ``u'?'``.

        """
        return filter(None,
            [getattr(m.syntacticCategory, 'name', None) for m in morphemeMatches] +
            [getattr(g.syntacticCategory, 'name', None) for g in glossMatches] + [u'?'])[0]

    def getBreakGlossCategory(morphemeDelimiters, morphemeBreak, morphemeGloss,
                              syntacticCategoryString, bgcDelimiter):
        """Return a ``breakGlossCategory`` string, e.g., u'le|the|Det-s|PL|Num chien|dog|N-s|PL|Num'."""
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
        """Return ``quadruple`` as a form-like object.
        
        :param tuple quadruple: ``(id, mb, mg, sc)``.
        :returns: a :class:`FakeForm` instance.

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
        """Return the list of forms that perfectly match a given morpheme.
        
        That is, return all forms ``f`` such that ``f.morphemeBreak==morpheme``
        *and* ``f.morphemeGloss==gloss``.

        If one of ``lexicalItems`` or ``deletedLexicalItems`` is truthy, then
        the result is generated using only those lists plus the existing
        references ``form.morphemeBreakIDs`` and ``form.morphemeGlossIDs``.
        This facilitates lexical change percolation while eliminating
        unnecessary database requests.  Note that the presence of a non-empty
        ``lexicalItems`` or ``deletedLexicalItems`` list implies that the
        supplied forms represent the only changes to the database relevant to
        the morphological analysis of ``form``.

        One complication arises from the fact that perfect matches mask partial
        ones.  If :func:`getPerfectMatches` removes the only perfect matches for
        a given morpheme, then it is possible that there are partial matches not
        listed in ``lexicalItems``.  Therefore, :ref:`getPartialMatches` must be
        made to query the database *only* when the morpheme in question is
        encountered.  This message is passed to :ref:`getPartialMatches` by
        returning an ordered pair (tuple) containing the newly match-less
        morpheme instead of the usual list of matches.

        :param form: the form model whose morphological analysis-related attributes are being generated.
        :param int wordIndex: the index of the word containing the morpheme being analyzed.
        :param int morphemeIndex: the index, within the word, of the morpheme being analyzed.
        :param str morpheme: the transcription of the morpheme.
        :param str gloss: the gloss of the morpheme.
        :param dict matchesFound: keys are morpheme 2-tuples and values are lists of matches.
        :param list lexicalItems: forms constituting the exclusive pool of potential matches.
        :param list deletedLexicalItems: forms that must be deleted from the matches.
        :returns: an ordered pair (tuple), where the second element is always
            the (potentially updated) ``matchesFound`` dictionary.  In the
            normal case, the first element is the list of perfect matches for
            the input morpheme.  When it is necessary to force
            :func:`getPartialMatches` to query the database, the first element
            of the return value is the ``(morpheme, gloss)`` tuple representing
            the morpheme.

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
        """Return the list of forms that partially match a given morpheme.
        
        If ``kwargs['morpheme']`` is present, return all forms ``f`` such that
        ``f.morphemeBreak==kwargs['morpheme']``; else if ``kwargs['gloss']`` is
        present, return all forms such that
        ``f.morphemeGloss==kwargs['gloss']``.

        If ``kwargs['lexicalItems']`` or ``kwargs['deletedLexicalItems']`` are
        present, then that list of forms will be used to build the list of
        partial matches and database will, usually, not be queried, cf.
        :func:`getPerfectMatches` above.  The only case where the db will be
        queried (when ``lexicalItems`` or ``deletedLexicalItems`` are supplied)
        is when ``kwargs['morpheme']`` or ``kwargs['gloss']`` is in
        ``forceQuery``.  When this is so, it indicates that
        :func:`getPerfectMatches` is communicating that the supplied lexical
        info resulted in all perfect matches for the given morpheme being
        emptied and that, therefore, the database must be searched for partial
        matches.

        :param form: the form model whose morphological analysis-related attributes are being generated.
        :param int wordIndex: the index of the word containing the morpheme being analyzed.
        :param int morphemeIndex: the index, within the word, of the morpheme being analyzed.
        :param dict matchesFound: keys are morpheme 2-tuples and values are lists of matches.
        :param str kwargs['morpheme']: the phonemic representation of the morpheme, if present.
        :param str kwargs['gloss']: the gloss of the morpheme, if present.
        :param list kwargs['lexicalItems']: forms constituting the exclusive pool of potential matches.
        :param list kwargs['deletedLexicalItems']: forms that must be deleted from the matches.
        :param iterable kwargs['forceQuery']: a 2-tuple representing a morpheme or a list of perfect matches.
        :returns: an ordered pair (tuple), where the first element is the list
            of partial matches found and the second is the (potentially updated)
            ``matchesFound`` dictionary.

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
    """Update the morphological analysis-related attributes of every form containing the input form as morpheme.
    
    Update the values of the ``morphemeBreadIDs``, ``morphemeGlossIDs``,
    ``syntacticCategoryString``, and ``breakGlossCategory`` attributes of each
    form that contains the input form in its morphological analysis, i.e., each
    form whose ``morphemeBreak`` value contains the input form's
    ``morphemeBreak`` value as a morpheme or whose ``morphemeGloss`` value
    contains the input form's ``morphemeGloss`` line as a gloss.  If the input
    form is not lexical (i.e., if it contains the space character or a
    morpheme delimiter), then no updates occur.

    :param form: a form model object.
    :param str change: indicates whether the form has just been deleted or created/updated.
    :param dict previousVersion: a representation of the form prior to update.
    :returns: ``None``

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
    """Return ``True`` if the update from formDict to form has changed the morphological analysis of the form."""
    try:
        oldSyntacticCategoryName = formDict['syntacticCategory'].get('name')
    except AttributeError:
        oldSyntacticCategoryName = None
    return form.morphemeBreak != formDict['morphemeBreak'] or \
           form.morphemeGloss != formDict['morphemeGloss'] or \
           form.breakGlossCategory != formDict['breakGlossCategory'] or \
           getattr(form.syntacticCategory, 'name', None) != oldSyntacticCategoryName


def updateCollectionsReferencingThisForm(form):
    """Update all collections that reference the input form in their ``contents`` value.

    When a form is deleted, it is necessary to update all collections whose
    ``contents`` value references the deleted form.  The update removes the
    reference, recomputes the ``contentsUnpacked``, ``html`` and ``forms``
    attributes of the affected collection and causes all of these changes to
    percolate through the collection-collection reference chain.

    :param form: a form model object
    :returns: ``None``

    .. note::
    
       Getting the collections that reference this form by searching for those
       whose ``forms`` attribute contain it is not quite the correct way to do
       this because many of these collections will not *directly* reference this
       form -- in short, this will result in redundant updates and backups.

    """
    pattern = unicode(h.formReferencePattern.pattern.replace('[0-9]+', str(form.id)))
    collectionsReferencingThisForm = Session.query(Collection).\
        filter(Collection.contents.op('regexp')(pattern)).all()
    for collection in collectionsReferencingThisForm:
        updateCollectionByDeletionOfReferencedForm(collection, form)
