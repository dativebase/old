import logging
import datetime
import re
import simplejson as json
from uuid import uuid4

from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from old.lib.base import BaseController
from old.lib.schemata import FormSchema, FormIdsSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Form, FormBackup, Gloss, User

log = logging.getLogger(__name__)

class FormsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol."""

    queryBuilder = SQLAQueryBuilder(config=config)

    @h.OLDjsonify
    @restrict('SEARCH', 'POST')
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
            query = h.filterRestrictedModels('Form', SQLAQuery)
            return h.addPagination(query, pythonSearchParams.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        # SQLAQueryBuilder should have captured these exceptions (and packed
        # them into an OLDSearchParseError) or sidestepped them, but here we'll
        # handle any that got past -- just in case.
        except (OperationalError, AttributeError, InvalidRequestError, RuntimeError):
            response.status_int = 400
            return {'error': u'The specified search parameters generated an invalid database query'}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /forms: Return all forms."""
        try:
            query = Session.query(Form)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels('Form', query)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.OLDjsonify
    @restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """POST /forms: Create a new form."""
        try:
            schema = FormSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.getStateObject(values)
            data = schema.to_python(values, state)
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        else:
            form = createNewForm(data)
            Session.add(form)
            Session.commit()
            updateApplicationSettingsIfFormIsForeignWord(form)
            return form

    @h.OLDjsonify
    @restrict('GET')
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

    @h.OLDjsonify
    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /forms/id: Update an existing form."""
        form = Session.query(Form).get(int(id))
        if form:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, form, unrestrictedUsers):
                try:
                    schema = FormSchema()
                    values = json.loads(unicode(request.body, request.charset))
                    state = h.getStateObject(values)
                    data = schema.to_python(values, state)
                except h.JSONDecodeError:
                    response.status_int = 400
                    return h.JSONDecodeErrorResponse
                except Invalid, e:
                    response.status_int = 400
                    return {'errors': e.unpack_errors()}
                else:
                    formDict = form.getDict()
                    form = updateForm(form, data)
                    # form will be False if there are no changes (cf. updateForm).
                    if form:
                        backupForm(formDict, form.datetimeModified)
                        Session.add(form)
                        Session.commit()
                        updateApplicationSettingsIfFormIsForeignWord(form)
                        return form
                    else:
                        response.status_int = 400
                        return {'error':
                            u'The update request failed because the submitted data were not new.'}
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no form with id %s' % id}

    @h.OLDjsonify
    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /forms/id: Delete an existing form.  Only the enterer and
        administrators can delete a form.
        """
        form = Session.query(Form).get(id)
        if form:
            if session['user'].role == u'administrator' or \
            form.enterer is session['user']:
                formDict = form.getDict()
                backupForm(formDict)
                Session.delete(form)
                Session.commit()
                updateApplicationSettingsIfFormIsForeignWord(form)
                return form
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no form with id %s' % id}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /forms/id: Return a JSON object representation of the form with
        id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """
        form = Session.query(Form).get(id)
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

    @h.OLDjsonify
    @restrict('GET')
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
        form = Session.query(Form).get(id)
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

    @h.OLDjsonify
    @restrict('GET')
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

    @h.OLDjsonify
    @restrict('POST')
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
                    Session.commit()
                    return [f.id for f in unrestrictedForms]
                else:
                    response.status_int = 403
                    return h.unauthorizedMsg
            else:
                response.status_int = 404
                return {'error': u'No valid form ids were provided.'}

    @h.OLDjsonify
    @restrict('PUT')
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
        """
        validDelimiters = h.getMorphemeDelimiters()
        forms = h.getForms()
        updatedFormIds = []
        for form in forms:
            formDict = form.getDict()
            form = updateMorphemeReferencesOfForm(form, validDelimiters)
            # form will be False if there are no changes.
            if form:
                backupForm(formDict, form.datetimeModified)
                Session.add(form)
                Session.commit()
                updateApplicationSettingsIfFormIsForeignWord(form)
                updatedFormIds.append(form.id)
        return updatedFormIds


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
        'elicitationMethods': h.getElicitationMethods,
        'tags': h.getTags,
        'syntacticCategories': h.getSyntacticCategories,
        'speakers': h.getSpeakers,
        'users': h.getUsers,
        'sources': h.getSources
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


def getMorphemeIDLists(form, validDelimiters=None):
    """This function generates values for the morphemeBreakIDs,
    morphemeGlossIDs and syntacticCategoryString attributes of the input form.
    It takes the morphemes and morpheme glosses of the Form and looks for
    matches in other (lexical) Forms.

    Specifically, it looks for Forms whose transcription matches the morpheme
    string and whose morphemeGloss matches the gloss string.  First it looks
    for perfect matches (i.e., a Form whose morphemeBreak matches the
    morpheme and whose morphemeGloss matches the gloss) and if none are
    found it looks for "half-matches" and if none of those are found, then
    form.morhemeBreakIDs and form.morhemeGlossIDs are empty lists.

    If any kind of match is found, the id, morpheme/gloss and syntactic
    category of the matching Forms are stored in a list of tuples:
    (id, mb/gl, sc).
    """

    morphemeBreakIDs = []
    morphemeGlossIDs = []
    syncatStr = []

    # Get the valid morpheme/gloss delimiters, e.g., '-', '=', ' ', as a
    #  disjunctive regex
    if not validDelimiters:
        validDelimiters = h.getMorphemeDelimiters()
    if validDelimiters:
        patt = u'[%s]' % ''.join([h.escREMetaChars(d) for d in validDelimiters])
    else:
        patt = u''

    if validDelimiters and form.morphemeBreak and form.morphemeGloss and \
    len(form.morphemeBreak.split()) == len(form.morphemeGloss.split()) and \
    [len(re.split(patt, x)) for x in form.morphemeBreak.split()] == \
    [len(re.split(patt, x)) for x in form.morphemeGloss.split()]:
        morphemeBreak = form.morphemeBreak
        morphemeGloss = form.morphemeGloss
        mbWords = morphemeBreak.split()
        mgWords = morphemeGloss.split()
        scWords = morphemeBreak.split()[:]
        for i in range(len(mbWords)):
            mbWordIDList = []
            mgWordIDList = []
            mbWord = mbWords[i]
            mgWord = mgWords[i]
            scWord = scWords[i]
            patt = '([%s])' % ''.join(validDelimiters)
            mbWordMorphemesList = re.split(patt, mbWord)[::2] 
            mgWordMorphemesList = re.split(patt, mgWord)[::2]
            scWordMorphemesList = re.split(patt, scWord)
            for ii in range(len(mbWordMorphemesList)):
                morpheme = mbWordMorphemesList[ii]
                gloss = mgWordMorphemesList[ii]
                matches = []
                if morpheme and gloss:
                    matches = Session.query(Form).filter(
                        Form.morphemeBreak==morpheme).filter(
                        Form.morphemeGloss==gloss).all()
                # If one or more Forms match both gloss and morpheme, append a
                #  list of the IDs of those Forms in morphemeBreakIDs and
                #  morphemeGlossIDs
                if matches:
                    mbWordIDList.append([f.syntacticCategory and
                        (f.id, f.morphemeGloss, f.syntacticCategory.name) 
                        or (f.id, f.morphemeGloss, None) for f in matches])
                    mgWordIDList.append([f.syntacticCategory and
                        (f.id, f.morphemeBreak, f.syntacticCategory.name) 
                        or (f.id, f.morphemeBreak, None) for f in matches])
                    scWordMorphemesList[ii * 2] = matches[0].syntacticCategory and \
                    matches[0].syntacticCategory.name or '?'
                # Otherwise, look for Forms that match only gloss or only
                #  morpheme and append respectively
                else:
                    morphemeMatches = []
                    if morpheme:
                        morphemeMatches = Session.query(Form).filter(
                            Form.morphemeBreak==morpheme).all()
                    if morphemeMatches:
                        mbWordIDList.append([f.syntacticCategory and
                            (f.id, f.morphemeGloss, f.syntacticCategory.name) 
                            or (f.id, f.morphemeGloss, None)
                            for f in morphemeMatches])
                    else:
                        mbWordIDList.append([])
                    glossMatches = []
                    if gloss:
                        glossMatches = Session.query(Form).filter(
                            Form.morphemeGloss==gloss).all()
                    if glossMatches:
                        mgWordIDList.append([f.syntacticCategory and
                            (f.id, f.morphemeBreak, f.syntacticCategory.name)
                            or (f.id, f.morphemeBreak, None)
                            for f in glossMatches])
                    else:
                        mgWordIDList.append([])
                    scWordMorphemesList[ii * 2] = '?'
            morphemeBreakIDs.append(mbWordIDList)
            morphemeGlossIDs.append(mgWordIDList)
            syncatStr.append(''.join(scWordMorphemesList))
    else:
        morphemeBreakIDs = [[[]]]
        morphemeGlossIDs = [[[]]]
        syncatStr = []
    # Convert the data structure into JSON for storage as a string in the DB
    return (
        unicode(json.dumps(morphemeBreakIDs)),
        unicode(json.dumps(morphemeGlossIDs)),
        unicode(' '.join(syncatStr))
    )


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
        form = Session.query(Form).get(id)
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

def createNewGloss(data):
    gloss = Gloss()
    gloss.gloss = h.toSingleSpace(h.normalize(data['gloss']))
    gloss.glossGrammaticality = data['glossGrammaticality']
    return gloss


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

    # User-entered date: dateElicited
    form.dateElicited = data['dateElicited']

    # One-to-Many Data: Glosses
    form.glosses = [createNewGloss(g) for g in data['glosses'] if g['gloss']]

    # Many-to-One
    if data['elicitationMethod']:
        form.elicitationMethod = data['elicitationMethod']
    if data['syntacticCategory']:
        form.syntacticCategory = data['syntacticCategory']
    if data['source']:
        form.source = data['source']
    if data['elicitor']:
        form.elicitor = data['elicitor']
    if data['verifier']:
        form.verifier = data['verifier']
    if data['speaker']:
        form.speaker = data['speaker']

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
    form.enterer = Session.query(User).get(session['user'].id)

    # Create the morphemeBreakIDs and morphemeGlossIDs attributes.
    # We add the form first to get an ID so that monomorphemic Forms can be
    # self-referential.
    Session.add(form)
    form.morphemeBreakIDs, form.morphemeGlossIDs, form.syntacticCategoryString = \
                                                        getMorphemeIDLists(form)
    return form

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updateForm function
# below.
CHANGED = None

def updateForm(form, data):
    """Update the input Form model object given a data dictionary provided by
    the user (as a JSON object).  If CHANGED is not set to true in the course
    of attribute setting, then None is returned and no update occurs.
    """

    global CHANGED

    def setAttr(obj, name, value):
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            global CHANGED
            CHANGED = True

    # Unicode Data
    setAttr(form, 'transcription',
            h.toSingleSpace(h.normalize(data['transcription'])))
    setAttr(form, 'phoneticTranscription',
            h.toSingleSpace(h.normalize(data['phoneticTranscription'])))
    setAttr(form, 'narrowPhoneticTranscription',
            h.toSingleSpace(h.normalize(data['narrowPhoneticTranscription'])))
    setAttr(form, 'morphemeBreak',
            h.toSingleSpace(h.normalize(data['morphemeBreak'])))
    setAttr(form, 'morphemeGloss',
            h.toSingleSpace(h.normalize(data['morphemeGloss'])))
    setAttr(form, 'comments', h.normalize(data['comments']))
    setAttr(form, 'speakerComments', h.normalize(data['speakerComments']))
    setAttr(form, 'grammaticality', data['grammaticality'])

    # User-entered date: dateElicited
    if form.dateElicited != data['dateElicited']:
        form.dateElicited = data['dateElicited']
        CHANGED = True

    # One-to-Many Data: Glosses
    # First check if the user has made any changes to the glosses.
    # If there are changes, then delete all glosses and replace with new
    #  ones.  (Note: this will result in the deletion of a gloss and the
    #  recreation of an identical one with a different index.  There may be a
    #  "better" way of doing this, but this way is simple...
    glossesToAdd = [(gloss['gloss'], gloss['glossGrammaticality'])
                    for gloss in data['glosses'] if gloss['gloss']]
    glossesWeHave = [(gloss.gloss, gloss.glossGrammaticality)
                    for gloss in form.glosses]
    if glossesToAdd != glossesWeHave:
        form.glosses = [createNewGloss(g) for g in data['glosses']
                        if g['gloss']]
        CHANGED = True

    # Many-to-One Data
    if data['elicitationMethod'] != form.elicitationMethod:
        form.elicitationMethod = data['elicitationMethod']
        CHANGED = True
    if data['syntacticCategory'] != form.syntacticCategory:
        form.syntacticCategory = data['syntacticCategory']
        CHANGED = True
    if data['source'] != form.source:
        form.source = data['source']
        CHANGED = True
    if data['elicitor'] != form.elicitor:
        form.elicitor = data['elicitor']
        CHANGED = True
    if data['verifier'] != form.verifier:
        form.verifier = data['verifier']
        CHANGED = True
    if data['speaker'] != form.speaker:
        form.speaker = data['speaker']
        CHANGED = True

    # Many-to-Many Data: tags & files
    # Update only if the user has made changes.
    filesToAdd = [f for f in data['files'] if f]
    tagsToAdd = [t for t in data['tags'] if t]

    if set(filesToAdd) != set(form.files):
        form.files = filesToAdd
        CHANGED = True

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
        CHANGED = True

    # Create the morphemeBreakIDs and morphemeGlossIDs attributes.
    morphemeBreakIDs, morphemeGlossIDs, syntacticCategoryString = \
                                                        getMorphemeIDLists(form)
    if morphemeBreakIDs != form.morphemeBreakIDs:
        form.morphemeBreakIDs = morphemeBreakIDs
        CHANGED = True
    if morphemeGlossIDs != form.morphemeGlossIDs:
        form.morphemeGlossIDs = morphemeGlossIDs
        CHANGED = True
    if syntacticCategoryString != form.syntacticCategoryString:
        form.syntacticCategoryString = syntacticCategoryString
        CHANGED = True

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        form.datetimeModified = datetime.datetime.utcnow()
        return form
    return CHANGED


def updateMorphemeReferencesOfForm(form, validDelimiters=None):
    """This function behaves just like updateForm() above except that it doesn't
    take any content-ful input -- it just tries to update the morpheme reference
    data.
    """

    global CHANGED

    # Attempt to recreate the morphemeBreakIDs, morphemeGlossIDs and
    # syntacticCategoryString attributes.
    morphemeBreakIDs, morphemeGlossIDs, syntacticCategoryString = \
                                    getMorphemeIDLists(form, validDelimiters)
    if morphemeBreakIDs != form.morphemeBreakIDs:
        form.morphemeBreakIDs = morphemeBreakIDs
        CHANGED = True
    if morphemeGlossIDs != form.morphemeGlossIDs:
        form.morphemeGlossIDs = morphemeGlossIDs
        CHANGED = True
    if syntacticCategoryString != form.syntacticCategoryString:
        form.syntacticCategoryString = syntacticCategoryString
        CHANGED = True

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        form.datetimeModified = datetime.datetime.utcnow()
        return form

    return CHANGED
