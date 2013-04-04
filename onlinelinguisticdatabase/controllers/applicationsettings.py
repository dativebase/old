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

"""Contains the :class:`ApplicationsettingsController` and its auxiliary functions.

.. module:: applicationsettings
   :synopsis: Contains the application settings controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, app_globals
from formencode.validators import Invalid
from sqlalchemy.sql import asc
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import ApplicationSettingsSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import ApplicationSettings

log = logging.getLogger(__name__)


class ApplicationsettingsController(BaseController):
    """Generate responses to requests on application settings resources.

    REST Controller styled on the Atom Publishing Protocol.

    The most recently created application settings resource is considered to be
    the *active* one.

    .. note::

       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    .. note::

       Only administrators are authorized to create, update or delete
       application settings resources.

    """

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all application settings resources.

        :URL: ``GET /applicationsettings``
        :returns: a list of all application settings resources.

        """
        return h.eagerloadApplicationSettings(
            Session.query(ApplicationSettings)).order_by(
                asc(ApplicationSettings.id)).all()

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator'])
    def create(self):
        """Create a new application settings resource and return it.

        :URL: ``POST /applicationsettings``
        :request body: JSON object representing the application settings to create.
        :returns: the newly created application settings.

        """
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

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator'])
    def new(self):
        """Return the data necessary to create a new application settings.

        :URL: ``GET /applicationsettings/new`` with optional query string parameters
        :returns: A dictionary of lists of resources

        .. note::

           See :func:`getNewApplicationSettingsData` to understand how the 
           query string parameters can affect the contents of the lists in the
           returned dictionary.

        """
        return getNewApplicationSettingsData(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator'])
    def update(self, id):
        """Update an application settings and return it.
        
        :URL: ``PUT /applicationsettings/id``
        :Request body: JSON object representing the application settings with updated attribute values.
        :param str id: the ``id`` value of the application settings to be updated.
        :returns: the updated application settings model.

        """
        applicationSettings = h.eagerloadApplicationSettings(
            Session.query(ApplicationSettings)).get(int(id))
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

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator'])
    def delete(self, id):
        """Delete an existing application settings and return it.

        :URL: ``DELETE /applicationsettings/id``
        :param str id: the ``id`` value of the application settings to be deleted.
        :returns: the deleted application settings model.

        """
        applicationSettings = h.eagerloadApplicationSettings(
            Session.query(ApplicationSettings)).get(id)
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

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return an application settings.
        
        :URL: ``GET /applicationsettings/id``
        :param str id: the ``id`` value of the application settings to be returned.
        :returns: an application settings model object.

        """
        applicationSettings = h.eagerloadApplicationSettings(
            Session.query(ApplicationSettings)).get(id)
        if applicationSettings:
            return applicationSettings
        else:
            response.status_int = 404
            return {'error': 'There is no application settings with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator'])
    def edit(self, id):
        """Return an application settings and the data needed to update it.

        :URL: ``GET /applicationsettings/edit`` with optional query string parameters 
        :param str id: the ``id`` value of the application settings that will be updated.
        :returns: a dictionary of the form::

                {"applicationSettings": {...}, "data": {...}}

            where the value of the ``applicationSettings`` key is a dictionary
            representation of the application settings and the value of the
            ``data`` key is a dictionary containing the objects necessary to
            update an application settings, viz. the return value of
            :func:`ApplicationsettingsController.new`.

        .. note::
        
           This action can be thought of as a combination of
           :func:`ApplicationsettingsController.show` and
           :func:`ApplicationsettingsController.new`.  See
           :func:`getNewApplicationSettingsData` to understand how the query
           string parameters can affect the contents of the lists in the
           ``data`` dictionary.

        """

        applicationSettings = h.eagerloadApplicationSettings(
            Session.query(ApplicationSettings)).get(id)
        if applicationSettings:
            return {'data': getNewApplicationSettingsData(request.GET),
                    'applicationSettings': applicationSettings}
        else:
            response.status_int = 404
            return {'error': 'There is no application settings with id %s' % id}


def getNewApplicationSettingsData(GET_params):
    """Return the data necessary to create a new application settings or update an existing one.
    
    :param GET_params: the ``request.GET`` dictionary-like object generated by
        Pylons which contains the query string parameters of the request.
    :returns: A dictionary whose values are lists of objects needed to create or
        update application settings.

    If ``GET_params`` has no keys, then return all required data.  If
    ``GET_params`` does have keys, then for each key whose value is a non-empty
    string (and not a valid ISO 8601 datetime) add the appropriate list of
    objects to the return dictionary.  If the value of a key is a valid ISO 8601
    datetime string, add the corresponding list of objects *only* if the
    datetime does *not* match the most recent ``datetimeModified`` value of the
    resource.  That is, a non-matching datetime indicates that the requester has
    out-of-date data.

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
        'users': h.getMiniDictsGetter('User'),
        'orthographies': h.getMiniDictsGetter('Orthography'),
        'languages': h.getLanguages
    }

    result = h.getDataForNewAction(GET_params, getterMap, modelNameMap)

    return result


def createNewApplicationSettings(data):
    """Create a new application settings.

    :param dict data: the application settings to be created.
    :returns: an SQLAlchemy model object representing the application settings.

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
    applicationSettings.morphemeDelimiters = h.normalize(data['morphemeDelimiters'])
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


def updateApplicationSettings(applicationSettings, data):
    """Update an application settings.

    :param applicationSettings: the application settings model to be updated.
    :param dict data: representation of the updated application settings.
    :returns: the updated application settings model or, if ``changed`` has not
        been set to ``True``, then ``False``.

    """
    changed = False

    # Unicode Data
    changed = h.setAttr(applicationSettings, 'objectLanguageName', data['objectLanguageName'], changed)
    changed = h.setAttr(applicationSettings, 'objectLanguageId', data['objectLanguageId'], changed)
    changed = h.setAttr(applicationSettings, 'metalanguageName', data['metalanguageName'], changed)
    changed = h.setAttr(applicationSettings, 'metalanguageId', data['metalanguageId'], changed)
    changed = h.setAttr(applicationSettings, 'metalanguageInventory',
            h.normalize(h.removeAllWhiteSpace(data['metalanguageInventory'])), changed)
    changed = h.setAttr(applicationSettings, 'orthographicValidation',
            data['orthographicValidation'], changed)
    changed = h.setAttr(applicationSettings, 'narrowPhoneticInventory',
            h.normalize(h.removeAllWhiteSpace(data['narrowPhoneticInventory'])), changed)
    changed = h.setAttr(applicationSettings, 'narrowPhoneticValidation',
            data['narrowPhoneticValidation'], changed)
    changed = h.setAttr(applicationSettings, 'broadPhoneticInventory',
            h.normalize(h.removeAllWhiteSpace(data['broadPhoneticInventory'])), changed)
    changed = h.setAttr(applicationSettings, 'broadPhoneticValidation',
            data['broadPhoneticValidation'], changed)
    changed = h.setAttr(applicationSettings, 'morphemeBreakIsOrthographic',
            data['morphemeBreakIsOrthographic'], changed)
    changed = h.setAttr(applicationSettings, 'morphemeBreakValidation',
            data['morphemeBreakValidation'], changed)
    changed = h.setAttr(applicationSettings, 'phonemicInventory',
            h.normalize(h.removeAllWhiteSpace(data['phonemicInventory'])), changed)
    changed = h.setAttr(applicationSettings, 'morphemeDelimiters',
            h.normalize(data['morphemeDelimiters']), changed)
    changed = h.setAttr(applicationSettings, 'punctuation',
            h.normalize(h.removeAllWhiteSpace(data['punctuation'])), changed)
    changed = h.setAttr(applicationSettings, 'grammaticalities',
            h.normalize(h.removeAllWhiteSpace(data['grammaticalities'])), changed)

    # Many-to-One
    changed = h.setAttr(applicationSettings, 'storageOrthography', data['storageOrthography'], changed)
    changed = h.setAttr(applicationSettings, 'inputOrthography', data['inputOrthography'], changed)
    changed = h.setAttr(applicationSettings, 'outputOrthography', data['outputOrthography'], changed)

    # Many-to-Many Data: unrestrictedUsers
    # First check if the user has made any changes. If there are changes, just
    # delete all and replace with new.
    unrestrictedUsersToAdd = [u for u in data['unrestrictedUsers'] if u]
    if set(unrestrictedUsersToAdd) != set(applicationSettings.unrestrictedUsers):
        applicationSettings.unrestrictedUsers = unrestrictedUsersToAdd
        changed = True

    if changed:
        applicationSettings.datetimeModified = datetime.datetime.utcnow()
        return applicationSettings
    return changed
