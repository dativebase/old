import logging
import datetime
import simplejson as json
from pylons import request, response, session, app_globals
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.sql import desc, asc
from old.lib.base import BaseController
from old.lib.schemata import ApplicationSettingsSchema
import old.lib.helpers as h
from old.model.meta import Session
from old.model import ApplicationSettings, Orthography, User

log = logging.getLogger(__name__)

class ApplicationsettingsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol.
    
    Note: the application settings are an unusual resource.  There is only
    really one item that is relevant: the most recent one.
    """

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /applicationsettings: return all application settings models as
        JSON objects.
        """
        return Session.query(ApplicationSettings).order_by(asc(ApplicationSettings.id)).all()

    @h.OLDjsonify
    @restrict('POST')
    @h.authenticate
    @h.authorize(['administrator'])
    def create(self):
        """POST /applicationsettings: Create a new application settings record."""
        try:
            schema = ApplicationSettingsSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
            applicationSettings = createNewApplicationSettings(result)
            Session.add(applicationSettings)
            Session.commit()
            app_globals.applicationSettings = h.ApplicationSettings()
            return applicationSettings
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator'])
    def new(self):
        """GET /applicationsettings/new: Return the data necessary to create a new application settings.

        Return a JSON object with the following properties: 'languages',
        'users' and 'orthographies', the value of each of which is an array that
        is either empty or contains the appropriate objects.

        See the getNewApplicationSettingsData function to understand how the GET
        params can affect the contents of the arrays.
        """
        return getNewApplicationSettingsData(request.GET)

    @h.OLDjsonify
    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator'])
    def update(self, id):
        """PUT /applicationsettings/id: Update an existing application settings."""
        applicationSettings = Session.query(ApplicationSettings).get(int(id))
        if applicationSettings:
            try:
                schema = ApplicationSettingsSchema()
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                # Try to create an updated ApplicationSetting object.
                applicationSettings = updateApplicationSettings(applicationSettings, data)
                # applicationSettings will be False if there are no changes
                if applicationSettings:
                    Session.add(applicationSettings)
                    Session.commit()
                    app_globals.applicationSettings = h.ApplicationSettings()
                    return applicationSettings
                else:
                    response.status_int = 400
                    return {'error': 'The update request failed because the submitted data were not new.'}

            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no application settings with id %s' % id}

    @h.OLDjsonify
    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator'])
    def delete(self, id):
        """DELETE /applicationsettings/id: Delete an existing application settings."""
        applicationSettings = Session.query(ApplicationSettings).get(id)
        if applicationSettings:
            activeApplicationSettingsId = getattr(h.getApplicationSettings(), 'id', None)
            toBeDeletedApplicationSettingsId = applicationSettings.id
            Session.delete(applicationSettings)
            Session.commit()
            if activeApplicationSettingsId == toBeDeletedApplicationSettingsId:
                app_globals.applicationSettings = h.ApplicationSettings()
            return applicationSettings
        else:
            response.status_int = 404
            return {'error': 'There is no application settings with id %s' % id}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /applicationsettings/id: Return a JSON object representation of
        the application settings with id=id.

        If the id is invalid, 'null' (None) will be returned.  If the
        id is unspecified, a '404 Not Found' status code will be returned along
        with a JSON.stringified {error: '404 Not Found'} object (see the
        error.py controller).
        """
        applicationSettings = Session.query(ApplicationSettings).get(id)
        if applicationSettings:
            return applicationSettings
        else:
            response.status_int = 404
            return {'error': 'There is no application settings with id %s' % id}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator'])
    def edit(self, id):
        """GET /applicationsettings/id/edit: Return the data necessary to update
        an existing application settings, i.e., the application settings'
        properties and the necessary additional data, i.e., orthographies,
        languages, and users.

        This action can be thought of as a combination of the 'show' and 'new'
        actions.  The output will be a JSON object of the form

            {applicationSettings: {...}, data: {...}},

        where output.applicationSettings is an object containing the application
        settings' properties (cf. the output of show) and output.data is an
        object containing the data required to add a new application settings
        (cf. the output of new).

        GET parameters will affect the value of output.data in the same way as
        for the new action, i.e., no params will result in all the necessary
        output.data being retrieved from the db while specified params will
        result in selective retrieval (see getNewApplicationSettingsData for
        details).
        """
        applicationSettings = Session.query(ApplicationSettings).get(id)
        if applicationSettings:
            return {'data': getNewApplicationSettingsData(request.GET),
                    'applicationSettings': applicationSettings}
        else:
            response.status_int = 404
            return {'error': 'There is no application settings with id %s' % id}


def getNewApplicationSettingsData(GET_params):
    """Return the data necessary to create a new ApplicationSettings or update
    an existing one.  The GET_params parameter is the request.GET dictionary-
    like object generated by Pylons.

    If no parameters are provided (i.e., GET_params is empty), then retrieve all
    data (i.e., users, orthographies and languages) from the db and return them.

    If parameters are specified, then for each parameter whose value is a
    non-empty string (and is not a valid ISO 8601 datetime), retrieve and
    return the appropriate list of objects.

    If the value of a parameter is a valid ISO 8601 datetime string,
    retrieve and return the appropriate list of objects *only* if the
    datetime param does *not* match the most recent datetimeModified value
    of the relevant data store.  This makes sense because a non-match indicates
    that the requester has out-of-date data.
    """

    # modelNameMap maps param names to the OLD model objects from which they are
    # derived.
    modelNameMap = {
        'users': 'User',
        'orthographies': 'Orthography',
        'languages': 'Language'
    }

    # getterMap maps param names to getter functions that retrieve the
    # appropriate data from the db.
    getterMap = {
        'users': h.getUsers,
        'orthographies': h.getOrthographies,
        'languages': h.getLanguages
    }

    result = h.getDataForNewAction(GET_params, getterMap, modelNameMap)

    return result


def createNewApplicationSettings(data):
    """Create a new ApplicationSettings model object given a data dictionary
    provided by the user (as a JSON object).
    """

    # Create the applicationSettings model object.
    applicationSettings = ApplicationSettings()
    applicationSettings.objectLanguageName = data['objectLanguageName']
    applicationSettings.objectLanguageId = data['objectLanguageId']
    applicationSettings.metalanguageName = data['metalanguageName']
    applicationSettings.metalanguageId = data['metalanguageId']
    applicationSettings.metalanguageInventory = h.normalize(h.removeAllWhiteSpace(
        data['metalanguageInventory']))
    applicationSettings.orthographicValidation = data['orthographicValidation']
    applicationSettings.narrowPhoneticInventory = h.normalize(h.removeAllWhiteSpace(
        data['narrowPhoneticInventory']))
    applicationSettings.narrowPhoneticValidation = data['narrowPhoneticValidation']
    applicationSettings.broadPhoneticInventory = h.normalize(h.removeAllWhiteSpace(
        data['broadPhoneticInventory']))
    applicationSettings.broadPhoneticValidation = data['broadPhoneticValidation']
    applicationSettings.morphemeBreakIsOrthographic = data[
        'morphemeBreakIsOrthographic']
    applicationSettings.morphemeBreakValidation = data['morphemeBreakValidation']
    applicationSettings.phonemicInventory = h.normalize(h.removeAllWhiteSpace(
        data['phonemicInventory']))
    applicationSettings.morphemeDelimiters = h.normalize(h.removeAllWhiteSpace(
        data['morphemeDelimiters']))
    applicationSettings.punctuation = h.normalize(h.removeAllWhiteSpace(
        data['punctuation']))
    applicationSettings.grammaticalities = h.normalize(h.removeAllWhiteSpace(
        data['grammaticalities']))

    # Many-to-One
    if data['storageOrthography']:
        applicationSettings.storageOrthography = data['storageOrthography']
    if data['inputOrthography']:
        applicationSettings.inputOrthography = data['inputOrthography']
    if data['outputOrthography']:
        applicationSettings.outputOrthography = data['outputOrthography']

    # Many-to-Many Data: unrestrictedUsers
    applicationSettings.unrestrictedUsers = [u for u in data['unrestrictedUsers'] if u]

    return applicationSettings


# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the
# updateApplicationSettings function below.
CHANGED = None

def updateApplicationSettings(applicationSettings, data):
    """Update the input ApplicationSettings model object given a data dictionary
    provided by the user (as a JSON object).  If CHANGED is not set to true in
    the course of attribute setting, then None is returned and no update occurs.
    """

    global CHANGED

    def setAttr(obj, name, value):
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            global CHANGED
            CHANGED = True


    # Unicode Data
    setAttr(applicationSettings, 'objectLanguageName', data['objectLanguageName'])
    setAttr(applicationSettings, 'objectLanguageId', data['objectLanguageId'])
    setAttr(applicationSettings, 'metalanguageName', data['metalanguageName'])
    setAttr(applicationSettings, 'metalanguageId', data['metalanguageId'])
    setAttr(applicationSettings, 'metalanguageInventory',
            h.normalize(h.removeAllWhiteSpace(data['metalanguageInventory'])))
    setAttr(applicationSettings, 'orthographicValidation',
            data['orthographicValidation'])
    setAttr(applicationSettings, 'narrowPhoneticInventory',
            h.normalize(h.removeAllWhiteSpace(data['narrowPhoneticInventory'])))
    setAttr(applicationSettings, 'narrowPhoneticValidation',
            data['narrowPhoneticValidation'])
    setAttr(applicationSettings, 'broadPhoneticInventory',
            h.normalize(h.removeAllWhiteSpace(data['broadPhoneticInventory'])))
    setAttr(applicationSettings, 'broadPhoneticValidation',
            data['broadPhoneticValidation'])
    setAttr(applicationSettings, 'morphemeBreakIsOrthographic',
            data['morphemeBreakIsOrthographic'])
    setAttr(applicationSettings, 'morphemeBreakValidation',
            data['morphemeBreakValidation'])
    setAttr(applicationSettings, 'phonemicInventory',
            h.normalize(h.removeAllWhiteSpace(data['phonemicInventory'])))
    setAttr(applicationSettings, 'morphemeDelimiters',
            h.normalize(h.removeAllWhiteSpace(data['morphemeDelimiters'])))
    setAttr(applicationSettings, 'punctuation',
            h.normalize(h.removeAllWhiteSpace(data['punctuation'])))
    setAttr(applicationSettings, 'grammaticalities',
            h.normalize(h.removeAllWhiteSpace(data['grammaticalities'])))

    # Many-to-One
    if data['storageOrthography'] != applicationSettings.storageOrthography:
        applicationSettings.storageOrthography = data['storageOrthography']
        CHANGED = True
    if data['inputOrthography'] != applicationSettings.inputOrthography:
        applicationSettings.inputOrthography = data['inputOrthography']
        CHANGED = True
    if data['outputOrthography'] != applicationSettings.outputOrthography:
        applicationSettings.outputOrthography = data['outputOrthography']
        CHANGED = True

    # Many-to-Many Data: unrestrictedUsers
    # First check if the user has made any changes. If there are changes, just
    # delete all and replace with new.
    unrestrictedUsersToAdd = [u for u in data['unrestrictedUsers'] if u]
    if set(unrestrictedUsersToAdd) != set(applicationSettings.unrestrictedUsers):
        applicationSettings.unrestrictedUsers = unrestrictedUsersToAdd
        CHANGED = True

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        applicationSettings.datetimeModified = datetime.datetime.utcnow()
        return applicationSettings
    return CHANGED
