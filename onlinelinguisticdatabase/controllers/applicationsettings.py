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
        return h.eagerload_application_settings(
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
            application_settings = create_new_application_settings(result)
            Session.add(application_settings)
            Session.commit()
            app_globals.application_settings = h.ApplicationSettings()
            return application_settings
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

           See :func:`get_new_application_settings_data` to understand how the 
           query string parameters can affect the contents of the lists in the
           returned dictionary.

        """
        return get_new_application_settings_data(request.GET)

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
        application_settings = h.eagerload_application_settings(
            Session.query(ApplicationSettings)).get(int(id))
        if application_settings:
            try:
                schema = ApplicationSettingsSchema()
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                # Try to create an updated ApplicationSetting object.
                application_settings = update_application_settings(application_settings, data)
                # application_settings will be False if there are no changes
                if application_settings:
                    Session.add(application_settings)
                    Session.commit()
                    app_globals.application_settings = h.ApplicationSettings()
                    return application_settings
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
        application_settings = h.eagerload_application_settings(
            Session.query(ApplicationSettings)).get(id)
        if application_settings:
            active_application_settings_id = getattr(h.get_application_settings(), 'id', None)
            to_be_deleted_application_settings_id = application_settings.id
            Session.delete(application_settings)
            Session.commit()
            if active_application_settings_id == to_be_deleted_application_settings_id:
                app_globals.application_settings = h.ApplicationSettings()
            return application_settings
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
        application_settings = h.eagerload_application_settings(
            Session.query(ApplicationSettings)).get(id)
        if application_settings:
            return application_settings
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

                {"application_settings": {...}, "data": {...}}

            where the value of the ``application_settings`` key is a dictionary
            representation of the application settings and the value of the
            ``data`` key is a dictionary containing the objects necessary to
            update an application settings, viz. the return value of
            :func:`ApplicationsettingsController.new`.

        .. note::
        
           This action can be thought of as a combination of
           :func:`ApplicationsettingsController.show` and
           :func:`ApplicationsettingsController.new`.  See
           :func:`get_new_application_settings_data` to understand how the query
           string parameters can affect the contents of the lists in the
           ``data`` dictionary.

        """

        application_settings = h.eagerload_application_settings(
            Session.query(ApplicationSettings)).get(id)
        if application_settings:
            return {'data': get_new_application_settings_data(request.GET),
                    'application_settings': application_settings}
        else:
            response.status_int = 404
            return {'error': 'There is no application settings with id %s' % id}


def get_new_application_settings_data(GET_params):
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
    datetime does *not* match the most recent ``datetime_modified`` value of the
    resource.  That is, a non-matching datetime indicates that the requester has
    out-of-date data.

    """

    # model_name_map maps param names to the OLD model objects from which they are
    # derived.
    model_name_map = {
        'users': 'User',
        'orthographies': 'Orthography',
        'languages': 'Language'
    }

    # getter_map maps param names to getter functions that retrieve the
    # appropriate data from the db.
    getter_map = {
        'users': h.get_mini_dicts_getter('User'),
        'orthographies': h.get_mini_dicts_getter('Orthography'),
        'languages': h.get_languages
    }

    result = h.get_data_for_new_action(GET_params, getter_map, model_name_map)

    return result


def create_new_application_settings(data):
    """Create a new application settings.

    :param dict data: the application settings to be created.
    :returns: an SQLAlchemy model object representing the application settings.

    """

    # Create the application_settings model object.
    application_settings = ApplicationSettings()
    application_settings.object_language_name = data['object_language_name']
    application_settings.object_language_id = data['object_language_id']
    application_settings.metalanguage_name = data['metalanguage_name']
    application_settings.metalanguage_id = data['metalanguage_id']
    application_settings.metalanguage_inventory = h.normalize(h.remove_all_white_space(
        data['metalanguage_inventory']))
    application_settings.orthographic_validation = data['orthographic_validation']
    application_settings.narrow_phonetic_inventory = h.normalize(h.remove_all_white_space(
        data['narrow_phonetic_inventory']))
    application_settings.narrow_phonetic_validation = data['narrow_phonetic_validation']
    application_settings.broad_phonetic_inventory = h.normalize(h.remove_all_white_space(
        data['broad_phonetic_inventory']))
    application_settings.broad_phonetic_validation = data['broad_phonetic_validation']
    application_settings.morpheme_break_is_orthographic = data[
        'morpheme_break_is_orthographic']
    application_settings.morpheme_break_validation = data['morpheme_break_validation']
    application_settings.phonemic_inventory = h.normalize(h.remove_all_white_space(
        data['phonemic_inventory']))
    application_settings.morpheme_delimiters = h.normalize(data['morpheme_delimiters'])
    application_settings.punctuation = h.normalize(h.remove_all_white_space(
        data['punctuation']))
    application_settings.grammaticalities = h.normalize(h.remove_all_white_space(
        data['grammaticalities']))

    # Many-to-One
    if data['storage_orthography']:
        application_settings.storage_orthography = data['storage_orthography']
    if data['input_orthography']:
        application_settings.input_orthography = data['input_orthography']
    if data['output_orthography']:
        application_settings.output_orthography = data['output_orthography']

    # Many-to-Many Data: unrestricted_users
    application_settings.unrestricted_users = [u for u in data['unrestricted_users'] if u]

    return application_settings


def update_application_settings(application_settings, data):
    """Update an application settings.

    :param application_settings: the application settings model to be updated.
    :param dict data: representation of the updated application settings.
    :returns: the updated application settings model or, if ``changed`` has not
        been set to ``True``, then ``False``.

    """
    changed = False

    # Unicode Data
    changed = application_settings.set_attr('object_language_name', data['object_language_name'], changed)
    changed = application_settings.set_attr('object_language_id', data['object_language_id'], changed)
    changed = application_settings.set_attr('metalanguage_name', data['metalanguage_name'], changed)
    changed = application_settings.set_attr('metalanguage_id', data['metalanguage_id'], changed)
    changed = application_settings.set_attr('metalanguage_inventory',
            h.normalize(h.remove_all_white_space(data['metalanguage_inventory'])), changed)
    changed = application_settings.set_attr('orthographic_validation',
            data['orthographic_validation'], changed)
    changed = application_settings.set_attr('narrow_phonetic_inventory',
            h.normalize(h.remove_all_white_space(data['narrow_phonetic_inventory'])), changed)
    changed = application_settings.set_attr('narrow_phonetic_validation',
            data['narrow_phonetic_validation'], changed)
    changed = application_settings.set_attr('broad_phonetic_inventory',
            h.normalize(h.remove_all_white_space(data['broad_phonetic_inventory'])), changed)
    changed = application_settings.set_attr('broad_phonetic_validation',
            data['broad_phonetic_validation'], changed)
    changed = application_settings.set_attr('morpheme_break_is_orthographic',
            data['morpheme_break_is_orthographic'], changed)
    changed = application_settings.set_attr('morpheme_break_validation',
            data['morpheme_break_validation'], changed)
    changed = application_settings.set_attr('phonemic_inventory',
            h.normalize(h.remove_all_white_space(data['phonemic_inventory'])), changed)
    changed = application_settings.set_attr('morpheme_delimiters',
            h.normalize(data['morpheme_delimiters']), changed)
    changed = application_settings.set_attr('punctuation',
            h.normalize(h.remove_all_white_space(data['punctuation'])), changed)
    changed = application_settings.set_attr('grammaticalities',
            h.normalize(h.remove_all_white_space(data['grammaticalities'])), changed)

    # Many-to-One
    changed = application_settings.set_attr('storage_orthography', data['storage_orthography'], changed)
    changed = application_settings.set_attr('input_orthography', data['input_orthography'], changed)
    changed = application_settings.set_attr('output_orthography', data['output_orthography'], changed)

    # Many-to-Many Data: unrestricted_users
    # First check if the user has made any changes. If there are changes, just
    # delete all and replace with new.
    unrestricted_users_to_add = [u for u in data['unrestricted_users'] if u]
    if set(unrestricted_users_to_add) != set(application_settings.unrestricted_users):
        application_settings.unrestricted_users = unrestricted_users_to_add
        changed = True

    if changed:
        application_settings.datetime_modified = datetime.datetime.utcnow()
        return application_settings
    return changed
