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
from sqlalchemy import bindparam
from sqlalchemy.sql import asc, or_
from sqlalchemy.orm import subqueryload
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import FormSchema, FormIdsSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Form, FormBackup, Collection
from onlinelinguisticdatabase.controllers.oldcollections import update_collection_by_deletion_of_referenced_form

log = logging.getLogger(__name__)

class FormsController(BaseController):
    """Generate responses to requests on form resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder(config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of form resources matching the input JSON query.

        :URL: ``SEARCH /forms`` (or ``POST /forms/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        """
        try:
            json_search_params = unicode(request.body, request.charset)
            python_search_params = json.loads(json_search_params)
            SQLAQuery = self.query_builder.get_SQLA_query(python_search_params.get('query'))
            query = h.eagerload_form(SQLAQuery)
            query = h.filter_restricted_models('Form', SQLAQuery)
            return h.add_pagination(query, python_search_params.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except Exception, e:
            log.warn("%s's filter expression (%s) raised an unexpected exception: %s." % (
                h.get_user_full_name(session['user']), request.body, e))
            response.status_int = 400
            return {'error': u'The specified search parameters generated an invalid database query'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """Return the data necessary to search the form resources.

        :URL: ``GET /forms/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all form resources.

        :URL: ``GET /forms`` with optional query string parameters for ordering
            and pagination.
        :returns: a list of all form resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_form(Session.query(Form))
            query = h.add_order_by(query, dict(request.GET), self.query_builder)
            query = h.filter_restricted_models('Form', query)
            return h.add_pagination(query, dict(request.GET))
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
            state = h.get_state_object(values)
            data = schema.to_python(values, state)
            form = create_new_form(data)
            Session.add(form)
            Session.commit()
            update_application_settings_if_form_is_foreign_word(form)
            update_forms_containing_this_form_as_morpheme(form)
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
        
           See :func:`get_new_edit_form_data` to understand how the query string
           parameters can affect the contents of the lists in the returned
           dictionary.

        """
        return get_new_edit_form_data(request.GET)

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
        form = h.eagerload_form(Session.query(Form)).get(int(id))
        if form:
            unrestricted_users = h.get_unrestricted_users()
            user = session['user']
            if h.user_is_authorized_to_access_model(user, form, unrestricted_users):
                try:
                    schema = FormSchema()
                    values = json.loads(unicode(request.body, request.charset))
                    state = h.get_state_object(values)
                    data = schema.to_python(values, state)
                    form_dict = form.get_dict()
                    form = update_form(form, data)
                    # form will be False if there are no changes (cf. update_form).
                    if form:
                        backup_form(form_dict)
                        Session.add(form)
                        Session.commit()
                        update_application_settings_if_form_is_foreign_word(form)
                        if update_has_changed_the_analysis(form, form_dict):
                            update_forms_containing_this_form_as_morpheme(form, 'update', form_dict)
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
                return h.unauthorized_msg
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
        form = h.eagerload_form(Session.query(Form)).get(id)
        if form:
            if session['user'].role == u'administrator' or \
            form.enterer is session['user']:
                form_dict = form.get_dict()
                backup_form(form_dict)
                update_collections_referencing_this_form(form)
                Session.delete(form)
                Session.commit()
                update_application_settings_if_form_is_foreign_word(form)
                update_forms_containing_this_form_as_morpheme(form, 'delete')
                return form
            else:
                response.status_int = 403
                return h.unauthorized_msg
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
        form = h.eagerload_form(Session.query(Form)).get(id)
        if form:
            unrestricted_users = h.get_unrestricted_users()
            user = session['user']
            if h.user_is_authorized_to_access_model(user, form, unrestricted_users):
                return form
            else:
                response.status_int = 403
                return h.unauthorized_msg
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
           :func:`get_new_edit_form_data` to understand how the query string
           parameters can affect the contents of the lists in the ``data``
           dictionary.

        """
        form = h.eagerload_form(Session.query(Form)).get(id)
        if form:
            unrestricted_users = h.get_unrestricted_users()
            if h.user_is_authorized_to_access_model(session['user'], form, unrestricted_users):
                return {'data': get_new_edit_form_data(request.GET), 'form': form}
            else:
                response.status_int = 403
                return h.unauthorized_msg
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

                {"form": { ... }, "previous_versions": [ ... ]}

            where the value of the ``form`` key is the form whose history is
            requested and the value of the ``previous_versions`` key is a list of
            dictionaries representing previous versions of the form.

        """
        form, previous_versions = h.get_model_and_previous_versions('Form', id)
        if form or previous_versions:
            unrestricted_users = h.get_unrestricted_users()
            user = session['user']
            accessible = h.user_is_authorized_to_access_model
            unrestricted_previous_versions = [fb for fb in previous_versions
                                    if accessible(user, fb, unrestricted_users)]
            form_is_restricted = form and not accessible(user, form, unrestricted_users)
            previous_versions_are_restricted = previous_versions and not \
                unrestricted_previous_versions
            if form_is_restricted or previous_versions_are_restricted :
                response.status_int = 403
                return h.unauthorized_msg
            else :
                return {'form': form,
                        'previous_versions': unrestricted_previous_versions}
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
                accessible = h.user_is_authorized_to_access_model
                unrestricted_users = h.get_unrestricted_users()
                user = session['user']
                unrestricted_forms = [f for f in forms
                                     if accessible(user, f, unrestricted_users)]
                if unrestricted_forms:
                    session['user'].remembered_forms += unrestricted_forms
                    session['user'].datetime_modified = h.now()
                    Session.commit()
                    return [f.id for f in unrestricted_forms]
                else:
                    response.status_int = 403
                    return h.unauthorized_msg
            else:
                response.status_int = 404
                return {'error': u'No valid form ids were provided.'}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator'])
    def update_morpheme_references(self):
        """Update the morphological analysis-related attributes of all forms.

        That is, update the values of the ``morpheme_break_ids``,
        ``morpheme_gloss_ids``, ``syntactic_category_string`` and
        ``break_gloss_category`` attributes of every form in the database.

        :URL: ``PUT /forms/update_morpheme_references``
        :returns: a list of ids corresponding to the forms where the update
            caused a change in the values of the target attributes.

        .. warning::
        
           It should not be necessary to request the regeneration of morpheme
           references via this action since this should already be accomplished
           automatically by the calls to
           ``update_forms_containing_this_form_as_morpheme`` on all successful
           update, create and delete requests on form resources.  This action
           is, therefore, deprecated (read: use it with caution) and may be
           removed in future versions of the OLD.

        """
        forms = h.get_forms()
        return update_morpheme_references_of_forms(h.get_forms(), h.get_morpheme_delimiters(), whole_db=forms, make_backups=False)


def update_application_settings_if_form_is_foreign_word(form):
    """Update the transcription validation functionality of the active application settings if the input form is a foreign word.

    :param form: a form model object
    :returns: ``None``

    """

    if h.form_is_foreign_word(form):
        try:
            application_settings = getattr(app_globals, 'application_settings', None)
            application_settings.get_attributes()
        except AttributeError:
            app_globals.application_settings = h.ApplicationSettings()
        except NameError:
            pass


def get_new_edit_form_data(GET_params):
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
    *only* if the datetime does *not* match the most recent ``datetime_modified``
    value of the resource.  That is, a non-matching datetime indicates that the
    requester has out-of-date data.

    """
    # Map param names to the OLD model objects from which they are derived.
    param_name2model_name = {
        'grammaticalities': 'ApplicationSettings',
        'elicitation_methods': 'ElicitationMethod',
        'tags': 'Tag',
        'syntactic_categories': 'SyntacticCategory',
        'speakers': 'Speaker',
        'users': 'User',
        'sources': 'Source'
    }

    # map_ maps param names to functions that retrieve the appropriate data
    # from the db.
    map_ = {
        'grammaticalities': h.get_grammaticalities,
        'elicitation_methods': h.get_mini_dicts_getter('ElicitationMethod'),
        'tags': h.get_mini_dicts_getter('Tag'),
        'syntactic_categories': h.get_mini_dicts_getter('SyntacticCategory'),
        'speakers': h.get_mini_dicts_getter('Speaker'),
        'users': h.get_mini_dicts_getter('User'),
        'sources': h.get_mini_dicts_getter('Source')
    }

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in map_])

    # There are GET params, so we are selective in what we return.
    if GET_params:
        for key in map_:
            val = GET_params.get(key)
            # Proceed so long as val is not an empty string.
            if val:
                val_as_datetime_obj = h.datetime_string2datetime(val)
                if val_as_datetime_obj:
                    # Value of param is an ISO 8601 datetime string that
                    # does not match the most recent datetime_modified of the
                    # relevant model in the db: therefore we return a list
                    # of objects/dicts.  If the datetimes do match, this
                    # indicates that the requester's own stores are
                    # up-to-date so we return nothing.
                    if val_as_datetime_obj != \
                    h.get_most_recent_modification_datetime(
                    param_name2model_name[key]):
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

def backup_form(form_dict):
    """Backup a form.

    :param dict form_dict: a representation of a form model.
    :returns: ``None``

    """
    form_backup = FormBackup()
    form_backup.vivify(form_dict)
    Session.add(form_backup)


################################################################################
# Form Create & Update Functions
################################################################################

def create_new_form(data):
    """Create a new form.

    :param dict data: the form to be created.
    :returns: an SQLAlchemy model object representing the form.

    """
    form = Form()
    form.UUID = unicode(uuid4())

    # Unicode Data
    form.transcription = h.to_single_space(h.normalize(data['transcription']))
    form.phonetic_transcription = h.to_single_space(h.normalize(
                                            data['phonetic_transcription']))
    form.narrow_phonetic_transcription = h.to_single_space(h.normalize(
                                        data['narrow_phonetic_transcription']))
    form.morpheme_break = h.to_single_space(h.normalize(data['morpheme_break']))
    form.morpheme_gloss = h.to_single_space(h.normalize(data['morpheme_gloss']))
    form.comments = h.normalize(data['comments'])
    form.speaker_comments = h.normalize(data['speaker_comments'])
    form.syntax = h.normalize(data['syntax'])
    form.semantics = h.normalize(data['semantics'])
    form.grammaticality = data['grammaticality']
    form.status = data['status']

    # User-entered date: date_elicited
    form.date_elicited = data['date_elicited']

    # Many-to-One
    form.elicitation_method = data['elicitation_method']
    form.syntactic_category = data['syntactic_category']
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
    tags = [tag for tag_list in tags for tag in tag_list]
    restricted_tags = [tag for tag in tags if tag.name == u'restricted']
    if restricted_tags:
        restricted_tag = restricted_tags[0]
        if restricted_tag not in form.tags:
            form.tags.append(restricted_tag)

    # OLD-generated Data
    form.datetime_entered = form.datetime_modified = h.now()
    form.enterer = form.modifier = session['user']

    # Create the morpheme_break_ids and morpheme_gloss_ids attributes.
    # We add the form first to get an ID so that monomorphemic Forms can be
    # self-referential.
    Session.add(form)
    (form.morpheme_break_ids, form.morpheme_gloss_ids, form.syntactic_category_string,
        form.break_gloss_category, cache) = compile_morphemic_analysis(form)
    return form

def update_form(form, data):
    """Update a form model.

    :param form: the form model to be updated.
    :param dict data: representation of the updated form.
    :returns: the updated form model or, if ``changed`` has not been set to
        ``True``, then ``False``.

    """
    changed = False
    # Unicode Data
    changed = form.set_attr('transcription',
            h.to_single_space(h.normalize(data['transcription'])), changed)
    changed = form.set_attr('phonetic_transcription',
            h.to_single_space(h.normalize(data['phonetic_transcription'])), changed)
    changed = form.set_attr('narrow_phonetic_transcription',
            h.to_single_space(h.normalize(data['narrow_phonetic_transcription'])), changed)
    changed = form.set_attr('morpheme_break',
            h.to_single_space(h.normalize(data['morpheme_break'])), changed)
    changed = form.set_attr('morpheme_gloss',
            h.to_single_space(h.normalize(data['morpheme_gloss'])), changed)
    changed = form.set_attr('comments', h.normalize(data['comments']), changed)
    changed = form.set_attr('speaker_comments', h.normalize(data['speaker_comments']), changed)
    changed = form.set_attr('syntax', h.normalize(data['syntax']), changed)
    changed = form.set_attr('semantics', h.normalize(data['semantics']), changed)
    changed = form.set_attr('grammaticality', data['grammaticality'], changed)
    changed = form.set_attr('status', data['status'], changed)

    # User-entered date: date_elicited
    changed = form.set_attr('date_elicited', data['date_elicited'], changed)

    # One-to-Many Data: Translations
    # First check if the user has made any changes to the translations.
    # If there are changes, then delete all translations and replace with new
    #  ones.  (Note: this will result in the deletion of a translation and the
    #  recreation of an identical one with a different index.  There may be a
    #  "better" way of doing this, but this way is simple...
    translations_we_have = [(t.transcription, t.grammaticality) for t in form.translations]
    translations_to_add = [(t.transcription, t.grammaticality) for t in data['translations']]
    if set(translations_we_have) != set(translations_to_add):
        form.translations = data['translations']
        changed = True

    # Many-to-One Data
    changed = form.set_attr('elicitation_method', data['elicitation_method'], changed)
    changed = form.set_attr('syntactic_category', data['syntactic_category'], changed)
    changed = form.set_attr('source', data['source'], changed)
    changed = form.set_attr('elicitor', data['elicitor'], changed)
    changed = form.set_attr('verifier', data['verifier'], changed)
    changed = form.set_attr('speaker', data['speaker'], changed)

    # Many-to-Many Data: tags & files
    # Update only if the user has made changes.
    files_to_add = [f for f in data['files'] if f]
    tags_to_add = [t for t in data['tags'] if t]

    if set(files_to_add) != set(form.files):
        form.files = files_to_add
        changed = True

        # Cause the entire form to be tagged as restricted if any one of its
        # files are so tagged.
        tags = [f.tags for f in form.files]
        tags = [tag for tag_list in tags for tag in tag_list]
        restricted_tags = [tag for tag in tags if tag.name == u'restricted']
        if restricted_tags:
            restricted_tag = restricted_tags[0]
            if restricted_tag not in tags_to_add:
                tags_to_add.append(restricted_tag)

    if set(tags_to_add) != set(form.tags):
        form.tags = tags_to_add
        changed = True

    # Create the morpheme_break_ids and morpheme_gloss_ids attributes.
    (morpheme_break_ids, morpheme_gloss_ids, syntactic_category_string,
        break_gloss_category, cache) = compile_morphemic_analysis(form)

    changed = form.set_attr('morpheme_break_ids', morpheme_break_ids, changed)
    changed = form.set_attr('morpheme_gloss_ids', morpheme_gloss_ids, changed)
    changed = form.set_attr('syntactic_category_string', syntactic_category_string, changed)
    changed = form.set_attr('break_gloss_category', break_gloss_category, changed)

    if changed:
        form.datetime_modified = h.now()
        session['user'] = Session.merge(session['user'])
        form.modifier = session['user']
        return form
    return changed


def update_morpheme_references_of_form(form, valid_delimiters=None, **kwargs):
    """Update the morphological analysis-related attributes of a form model.

    Attempt to update the values of the ``morpheme_break_ids``,
    ``morpheme_gloss_ids``, ``syntactic_category_string`` and ``break_gloss_category``
    attributes of a form using only the lexical items specified in the list
    ``kwargs['lexical_items']`` or the list ``kwargs['deleted_lexical_items']``.

    :param form: the form model to be updated.
    :param list valid_delimiters: morpheme delimiters as strings.
    :param list kwargs['lexical_items']: a list of form models.
    :param list kwargs['deleted_lexical_items']: a list of form models.
    :returns: the form if updated; else ``False``.

    """
    changed = False
    (morpheme_break_ids, morpheme_gloss_ids, syntactic_category_string,
        break_gloss_category, cache) = compile_morphemic_analysis(form, valid_delimiters, **kwargs)
    changed = form.set_attr('morpheme_break_ids', morpheme_break_ids, changed)
    changed = form.set_attr('morpheme_gloss_ids', morpheme_gloss_ids, changed)
    changed = form.set_attr('syntactic_category_string', syntactic_category_string, changed)
    changed = form.set_attr('break_gloss_category', break_gloss_category, changed)
    if changed:
        form.datetime_modified = h.now()
        session['user'] = Session.merge(session['user'])
        form.modifier = session['user']
        return form, cache
    return changed, cache

def update_morpheme_references_of_forms(forms, valid_delimiters, **kwargs):
    """Update the morphological analysis-related attributes of a list of form models.

    Attempt to update the values of the ``morpheme_break_ids``,
    ``morpheme_gloss_ids``, ``syntactic_category_string`` and ``break_gloss_category``
    attributes of all forms in ``forms``.  The ``kwargs`` dict may contain
    ``lexical_items``, ``deleted_lexical_items`` or ``whole_db`` values which will be
    passed to compile_morphemic_analysis.

    :param list forms: the form models to be updated.
    :param list valid_delimiters: morpheme delimiters as strings.
    :param list kwargs['lexical_items']: a list of form models.
    :param list kwargs['deleted_lexical_items']: a list of form models.
    :param list kwargs['whole_db']: a list of all the form models in the database.
    :returns: a list of form ``id`` values corresponding to the forms that have
        been updated.

    """
    form_buffer = []
    formbackup_buffer = []
    make_backups = kwargs.get('make_backups', True)
    modifier = session['user'] = Session.merge(session['user'])
    modifier_id = modifier.id
    modification_datetime = h.now()
    form_table = Form.__table__
    for form in forms:
        (morpheme_break_ids, morpheme_gloss_ids, syntactic_category_string,
            break_gloss_category, kwargs['cache']) = compile_morphemic_analysis(form, valid_delimiters, **kwargs)
        if (morpheme_break_ids, morpheme_gloss_ids, syntactic_category_string, break_gloss_category) != \
            (form.morpheme_break_ids, form.morpheme_gloss_ids, form.syntactic_category_string, form.break_gloss_category):
            form_buffer.append({
                'id_': form.id, 
                'morpheme_break_ids': utf8_encode(morpheme_break_ids),
                'morpheme_gloss_ids': utf8_encode(morpheme_gloss_ids),
                'syntactic_category_string': utf8_encode(syntactic_category_string),
                'break_gloss_category': utf8_encode(break_gloss_category),
                'modifier_id': modifier_id,
                'datetime_modified': modification_datetime
            })
            if make_backups:
                formbackup = FormBackup()
                formbackup.vivify(form.get_dict())
                formbackup_buffer.append(formbackup)
    if form_buffer:
        rdbms_name = h.get_RDBMS_name(config=config)
        if rdbms_name == 'mysql':
            Session.execute('set names utf8;')
        update = form_table.update().where(form_table.c.id==bindparam('id_')).\
                    values(**dict([(k, bindparam(k)) for k in form_buffer[0] if k != 'id_']))
        Session.execute(update, form_buffer)
    if make_backups and formbackup_buffer:
        Session.add_all(formbackup_buffer)
        Session.commit()
    return [f['id_'] for f in form_buffer]

def utf8_encode(unistr):
    try:
        return unistr.encode('utf8')
    except AttributeError:
        return None

def compile_morphemic_analysis(form, morpheme_delimiters=None, **kwargs):
    """An error-handling wrapper arround :func:`compileMorphemicAnalysis_`.

    Catch any error, log it and return a default 4-tuple.

    :param form: the form model for which the morphological values are to be generated.
    :param list valid_delimiters: morpheme delimiters as strings.
    :param dict kwargs: arguments that can affect the degree to which the database is queried.
    :returns: the output of :func:`compileMorphemicAnalysis_` or, if an error
        occurs, a 4-tuple of ``None`` objects.

    """
    try:
        return compileMorphemicAnalysis_(form, morpheme_delimiters, **kwargs)
    except Exception, e:
        log.debug('compile_morphemic_analysis raised an error (%s) on "%s"/"%s".' % (
            e, form.morpheme_break, form.morpheme_gloss))
        return None, None, None, None, {}

def compileMorphemicAnalysis_(form, morpheme_delimiters=None, **kwargs):
    """Generate values fo the morphological analysis-related attributes of a form model.

    :param form: the form model for which the morphological values are to be generated.
    :param list valid_delimiters: morpheme delimiters as strings.
    :param dict kwargs: arguments that can affect the degree to which the database is queried.
    :returns: a 4-tuple containing the generated values or all four ``None``
        objects if no values can be generated.

    Generate values for the ``morpheme_break_ids``, ``morpheme_gloss_ids``,
    ``syntactic_category_string`` and ``break_gloss_category`` attributes of the
    input form.

    For each morpheme detected in the ``form``, search the database for forms
    whose ``morpheme_break`` value matches the morpheme's phonemic form and whose
    ``morpheme_gloss`` value matches the morpheme's gloss.  If a perfect match is
    not found, search the database for forms matching just the phonemic form or
    just the gloss.

    Matching forms are represented as triples where the first element is the
    ``id`` value of the match, the second is its ``morpheme_break`` or
    ``morpheme_gloss`` value and the third is its ``syntactic_category.name``
    value.  To illustrate, consider a form with ``morpheme_break`` value
    u'chien-s' and ``morpheme_gloss`` value u'dog-PL' and assume the lexical
    entries 'chien/dog/N/33', 's/PL/Agr/103' and 's/PL/Num/111' (where, for
    */a/b/c/d*, *a* is the ``morpheme_break`` value, *b* is the ``morpheme_gloss``
    value, *c* is the ``syntactic_category.name`` value and *d* is the ``id``
    value.  Running :func:`compile_morphemic_analysis` on the target form returns
    the following 4-tuple ``q``::

        (
            json.dumps([[[[33, u'dog', u'N']], [[111, u'PL', u'Num'], [103, u'PL', u'Agr']]]]),
            json.dumps([[[[33, u'chien', u'N']], [[111, u's', u'Num'], [103, u's', u'Agr']]]]),
            u'N-Num',
            u'chien|dog|N-s|PL|Num'
        )

    where ``q[0]`` is the ``morpheme_break_ids`` value, ``q[1]`` is the
    ``morpheme_gloss_ids`` value, ``q[2]`` is ``syntactic_category_string`` value
    and ``q[3]`` is ``break_gloss_category`` value.

    If ``kwargs`` contains a 'lexical_items' or a 'deleted_lexical_items' key, then
    :func:`compile_morphemic_analysis` will *update* (i.e., not re-create) the 4
    relevant values of the form using only the items in
    ``kwargs['lexical_items']`` or ``kwargs['deleted_lexical_items']``.  This
    facilitates lexical change percolation without massively redundant database
    queries.

    """

    def join(bgc, morpheme_delimiters, bgc_delimiter):
        """Convert a break-gloss-category tuple into a delimited string.
        
        Join the break-gloss-category 3-tuple ``bgc`` using the delimiter
        string.  If ``bgc`` contains only morpheme/word delimiters, then the
        first such delimiter is returned::

        :param list bgc: the morpheme as phonemic form, gloss and category.
        :param list morpheme_delimiters: morpheme delimiters as strings.
        :param str bgc_delimiter: delimiter used to join the elements of the morpheme.
        :returns: a string representation of the morpheme.

            >>> join([u'le', u'the', u'Det'], [u'-', u'=', u' '], u'|')
            u'le|the|Det'

            >>> join([u'-', u'-', u'-'], [u'-', u'=', u' '], u'|')
            u'-'

            >>> join([u'=', u'-', u'='], [u'-', u'=', u' '], u'|')
            u'='

        """

        if (bgc[0] in morpheme_delimiters and bgc[1] in morpheme_delimiters and
            bgc[2] in morpheme_delimiters):
            return bgc[0]

        return bgc_delimiter.join(bgc)

    def morphemic_analysis_is_consistent(**kwargs):
        """Determine whether a morphemic analysis is consistent.

        :param dict kwargs: contains the morphological data in various pre-processed states.
        :returns: ``True`` if the morphemic analysis is consistent; ``False`` otherwise.

        "Consistent" means that the ``morpheme_break`` and ``morpheme_gloss``
        values of ``kargs`` are not empty, there are equal numbers of morpheme
        break and morpheme gloss "words" and each morpheme break word has the
        same number of morphemes as its morpheme gloss counterpart.

        """
        return (kwargs['morpheme_break'] != u'' and
            kwargs['morpheme_gloss'] != u'' and
            len(kwargs['mb_words']) == len(kwargs['mg_words']) and
            [len(re.split(kwargs['morpheme_splitter'], mbw)) for mbw in kwargs['mb_words']] ==
            [len(re.split(kwargs['morpheme_splitter'], mgw)) for mgw in kwargs['mg_words']])

    def get_category_from_partial_match(morpheme_matches, gloss_matches):
        """Return a syntactic category name for a partially matched morpheme.

        :param list morpheme_matches: forms matching the morpheme's transcription.
        :param list gloss_matches: forms matching the morpheme's gloss.
        :returns: the category name of the first morpheme match, else that of
            the first gloss match, else the value of ``h.unknown_category``, i.e,. ``u'?'``.

        """
        return filter(None,
            [getattr(m.syntactic_category, 'name', None) for m in morpheme_matches] +
            [getattr(g.syntactic_category, 'name', None) for g in gloss_matches] + [h.unknown_category])[0]

    def get_break_gloss_category(morpheme_delimiters, morpheme_break, morpheme_gloss,
                              syntactic_category_string, bgc_delimiter):
        """Return a ``break_gloss_category`` string, e.g., u'le|the|Det-s|PL|Num chien|dog|N-s|PL|Num'."""
        try:
            delimiters = [u' '] + morpheme_delimiters
            splitter = u'([%s])' % ''.join([h.esc_RE_meta_chars(d) for d in delimiters])
            mb_split = filter(None, re.split(splitter, morpheme_break))
            mg_split = filter(None, re.split(splitter, morpheme_gloss))
            sc_split = filter(None, re.split(splitter, syntactic_category_string))
            break_gloss_category = zip(mb_split, mg_split, sc_split)
            return u''.join([join(bgc, delimiters, bgc_delimiter) for bgc in break_gloss_category])
        except TypeError:
            return None

    def get_fake_form(quadruple):
        """Return ``quadruple`` as a form-like object.
        
        :param tuple quadruple: ``(id, mb, mg, sc)``.
        :returns: a :class:`FakeForm` instance.

        """
        class FakeForm(object):
            pass
        class FakeSyntacticCategory(object):
            pass
        fake_form = FakeForm()
        fake_syntactic_category = FakeSyntacticCategory()
        fake_syntactic_category.name = quadruple[3]
        fake_form.id = quadruple[0]
        fake_form.morpheme_break = quadruple[1]
        fake_form.morpheme_gloss = quadruple[2]
        fake_form.syntactic_category = fake_syntactic_category
        return fake_form

    def get_perfect_matches(form, word_index, morpheme_index, morpheme, gloss, matches_found,
                          lexical_items, deleted_lexical_items, whole_db):
        """Return the list of forms that perfectly match a given morpheme.
        
        That is, return all forms ``f`` such that ``f.morpheme_break==morpheme``
        *and* ``f.morpheme_gloss==gloss``.

        If one of ``lexical_items`` or ``deleted_lexical_items`` is truthy, then
        the result is generated using only those lists plus the existing
        references ``form.morpheme_break_ids`` and ``form.morpheme_gloss_ids``.
        This facilitates lexical change percolation while eliminating
        unnecessary database requests.  Note that the presence of a non-empty
        ``lexical_items`` or ``deleted_lexical_items`` list implies that the
        supplied forms represent the only changes to the database relevant to
        the morphological analysis of ``form``.

        One complication arises from the fact that perfect matches mask partial
        ones.  If :func:`get_perfect_matches` removes the only perfect matches for
        a given morpheme, then it is possible that there are partial matches not
        listed in ``lexical_items``.  Therefore, :ref:`get_partial_matches` must be
        made to query the database *only* when the morpheme in question is
        encountered.  This message is passed to :ref:`get_partial_matches` by
        returning an ordered pair (tuple) containing the newly match-less
        morpheme instead of the usual list of matches.

        :param form: the form model whose morphological analysis-related attributes are being generated.
        :param int word_index: the index of the word containing the morpheme being analyzed.
        :param int morpheme_index: the index, within the word, of the morpheme being analyzed.
        :param str morpheme: the transcription of the morpheme.
        :param str gloss: the gloss of the morpheme.
        :param dict matches_found: keys are morpheme 2-tuples and values are lists of matches.
        :param list lexical_items: forms constituting the exclusive pool of potential matches.
        :param list deleted_lexical_items: forms that must be deleted from the matches.
        :returns: an ordered pair (tuple), where the second element is always
            the (potentially updated) ``matches_found`` dictionary.  In the
            normal case, the first element is the list of perfect matches for
            the input morpheme.  When it is necessary to force
            :func:`get_partial_matches` to query the database, the first element
            of the return value is the ``(morpheme, gloss)`` tuple representing
            the morpheme.

        """
        if (morpheme, gloss) in matches_found:
            return matches_found[(morpheme, gloss)], matches_found
        if whole_db:
            result = [f for f in whole_db if f.morpheme_break == morpheme and f.morpheme_gloss == gloss]
        elif lexical_items or deleted_lexical_items:
            extant_morpheme_break_ids = json.loads(form.morpheme_break_ids)
            extant_morpheme_gloss_ids = json.loads(form.morpheme_gloss_ids)
            # Extract extant perfect matches as quadruples: (id, mb, mg, sc)
            extant_perfect_matches_originally = [(x[0][0], x[1][1], x[0][1], x[0][2])
                for x in zip(extant_morpheme_break_ids[word_index][morpheme_index],
                             extant_morpheme_gloss_ids[word_index][morpheme_index])
                if x[0][0] == x[1][0]]
            # Make extant matches look like form objects and remove those that
            # may have been deleted or updated
            extant_perfect_matches = [get_fake_form(m) for m in extant_perfect_matches_originally
                if m[0] not in [f.id for f in lexical_items + deleted_lexical_items]]
            perfect_matches_in_lexical_items = [f for f in lexical_items
                if f.morpheme_break == morpheme and f.morpheme_gloss == gloss]
            perfect_matches_now = sorted(extant_perfect_matches + perfect_matches_in_lexical_items,
                                       key=lambda f: f.id)
            # If perfect matches have been emptied by us, we return a tuple so that
            # get_partial_matches knows to query the database for this morpheme only
            if perfect_matches_now == [] and extant_perfect_matches_originally != []:
                return (morpheme, gloss), matches_found
            result = perfect_matches_now
        else:
            result = Session.query(Form)\
                .filter(Form.morpheme_break==morpheme)\
                .filter(Form.morpheme_gloss==gloss).order_by(asc(Form.id)).all()
        matches_found[(morpheme, gloss)] = result
        return result, matches_found

    def get_partial_matches(form, word_index, morpheme_index, matches_found, **kwargs):
        """Return the list of forms that partially match a given morpheme.
        
        If ``kwargs['morpheme']`` is present, return all forms ``f`` such that
        ``f.morpheme_break==kwargs['morpheme']``; else if ``kwargs['gloss']`` is
        present, return all forms such that
        ``f.morpheme_gloss==kwargs['gloss']``.

        If ``kwargs['lexical_items']`` or ``kwargs['deleted_lexical_items']`` are
        present, then that list of forms will be used to build the list of
        partial matches and database will, usually, not be queried, cf.
        :func:`get_perfect_matches` above.  The only case where the db will be
        queried (when ``lexical_items`` or ``deleted_lexical_items`` are supplied)
        is when ``kwargs['morpheme']`` or ``kwargs['gloss']`` is in
        ``force_query``.  When this is so, it indicates that
        :func:`get_perfect_matches` is communicating that the supplied lexical
        info resulted in all perfect matches for the given morpheme being
        emptied and that, therefore, the database must be searched for partial
        matches.

        :param form: the form model whose morphological analysis-related attributes are being generated.
        :param int word_index: the index of the word containing the morpheme being analyzed.
        :param int morpheme_index: the index, within the word, of the morpheme being analyzed.
        :param dict matches_found: keys are morpheme 2-tuples and values are lists of matches.
        :param str kwargs['morpheme']: the phonemic representation of the morpheme, if present.
        :param str kwargs['gloss']: the gloss of the morpheme, if present.
        :param list kwargs['lexical_items']: forms constituting the exclusive pool of potential matches.
        :param list kwargs['deleted_lexical_items']: forms that must be deleted from the matches.
        :param iterable kwargs['force_query']: a 2-tuple representing a morpheme or a list of perfect matches.
        :returns: an ordered pair (tuple), where the first element is the list
            of partial matches found and the second is the (potentially updated)
            ``matches_found`` dictionary.

        """
        lexical_items = kwargs.get('lexical_items')
        deleted_lexical_items = kwargs.get('deleted_lexical_items')
        whole_db = kwargs.get('whole_db')
        force_query = kwargs.get('force_query')   # The output of get_perfect_matches: [] or (morpheme, gloss)
        morpheme = kwargs.get('morpheme')
        gloss = kwargs.get('gloss')
        attribute = morpheme and u'morpheme_break' or u'morpheme_gloss'
        value = morpheme or gloss
        if (morpheme, gloss) in matches_found:
            return matches_found[(morpheme, gloss)], matches_found
        if whole_db:
            result = [f for f in whole_db if getattr(f, attribute) == value]
        elif lexical_items or deleted_lexical_items:
            if value in force_query:
                result = Session.query(Form)\
                        .filter(getattr(Form, attribute)==value).order_by(asc(Form.id)).all()
            else:
                extant_analyses = json.loads(getattr(form, attribute + '_ids'))[word_index][morpheme_index]
                # Extract extant partial matches as quadruples of the form (id, mb, mg, sc)
                # where one of mb or mg will be None.
                extant_partial_matches = [(x[0], None, x[1], x[2]) if morpheme else
                                    (x[0], x[1], None, x[2]) for x in extant_analyses]
                # Make extant matches look like form objects and remove those that
                # may have been deleted or updated
                extant_partial_matches = [get_fake_form(m) for m in extant_partial_matches
                    if m[0] not in [f.id for f in lexical_items + deleted_lexical_items]]
                partial_matches_in_lexical_items = [f for f in lexical_items
                                                if getattr(f, attribute) == value]
                result = sorted(extant_partial_matches + partial_matches_in_lexical_items,
                              key=lambda f: f.id)
        else:
            result = Session.query(Form).filter(getattr(Form, attribute)==value).order_by(asc(Form.id)).all()
        matches_found[(morpheme, gloss)] = result
        return result, matches_found

    bgc_delimiter = kwargs.get('bgc_delimiter', h.default_delimiter)     # The default delimiter for the break_gloss_category field
    lexical_items = kwargs.get('lexical_items', [])
    deleted_lexical_items = kwargs.get('deleted_lexical_items', [])
    matches_found = kwargs.get('cache', {})   # temporary store -- eliminates redundant queries & processing -- updated as a byproduct of get_perfect_matches and get_partial_matches
    whole_db = kwargs.get('whole_db')
    morpheme_break_ids = []
    morpheme_gloss_ids = []
    syntactic_category_string = []
    morpheme_delimiters = morpheme_delimiters or h.get_morpheme_delimiters()
    morpheme_splitter = morpheme_delimiters and u'[%s]' % ''.join(
                        [h.esc_RE_meta_chars(d) for d in morpheme_delimiters]) or u''
    morpheme_break = form.morpheme_break
    morpheme_gloss = form.morpheme_gloss
    mb_words = morpheme_break.split()     # e.g., u'le-s chien-s'
    mg_words = morpheme_gloss.split()     # e.g., u'the-PL dog-PL'
    sc_words = morpheme_break.split()[:]  # e.g., u'le-s chien-s' (placeholder)

    if morphemic_analysis_is_consistent(morpheme_delimiters=morpheme_delimiters,
        morpheme_break=morpheme_break, morpheme_gloss=morpheme_gloss, mb_words=mb_words,
        mg_words=mg_words, morpheme_splitter=morpheme_splitter):
        for i in range(len(mb_words)):
            mb_word_analysis = []
            mg_word_analysis = []
            mb_word = mb_words[i]     # e.g., u'chien-s'
            mg_word = mg_words[i]     # e.g., u'dog-PL'
            sc_word = sc_words[i]     # e.g., u'chien-s'
            morpheme_and_delimiter_splitter = '(%s)' % morpheme_splitter    # splits on delimiters while retaining them
            mb_word_morphemes_list = re.split(morpheme_and_delimiter_splitter, mb_word)[::2]   # e.g., ['chien', 's']
            mg_word_morphemes_list = re.split(morpheme_and_delimiter_splitter, mg_word)[::2]   # e.g., ['dog', 'PL']
            sc_word_analysis = re.split(morpheme_and_delimiter_splitter, sc_word)    # e.g., ['chien', '-', 's']
            for j in range(len(mb_word_morphemes_list)):
                morpheme = mb_word_morphemes_list[j]
                gloss = mg_word_morphemes_list[j]
                perfect_matches, matches_found = get_perfect_matches(form, i, j, morpheme, gloss,
                                            matches_found, lexical_items, deleted_lexical_items, whole_db)
                if perfect_matches and type(perfect_matches) is list:
                    mb_word_analysis.append([(f.id, f.morpheme_gloss,
                        getattr(f.syntactic_category, 'name', None)) for f in perfect_matches])
                    mg_word_analysis.append([(f.id, f.morpheme_break,
                        getattr(f.syntactic_category, 'name', None)) for f in perfect_matches])
                    sc_word_analysis[j * 2] = getattr(perfect_matches[0].syntactic_category, 'name', h.unknown_category)
                else:
                    morpheme_matches, matches_found = get_partial_matches(form, i, j, matches_found, morpheme=morpheme,
                                        force_query=perfect_matches, lexical_items=lexical_items,
                                        deleted_lexical_items=deleted_lexical_items, whole_db=whole_db)
                    if morpheme_matches:
                        mb_word_analysis.append([(f.id, f.morpheme_gloss,
                            getattr(f.syntactic_category, 'name', None)) for f in morpheme_matches])
                    else:
                        mb_word_analysis.append([])
                    gloss_matches, matches_found = get_partial_matches(form, i, j, matches_found, gloss=gloss,
                                        force_query=perfect_matches, lexical_items=lexical_items,
                                        deleted_lexical_items=deleted_lexical_items, whole_db=whole_db)
                    if gloss_matches:
                        mg_word_analysis.append([(f.id, f.morpheme_break,
                            getattr(f.syntactic_category, 'name', None)) for f in gloss_matches])
                    else:
                        mg_word_analysis.append([])
                    sc_word_analysis[j * 2] = get_category_from_partial_match(morpheme_matches, gloss_matches)
            morpheme_break_ids.append(mb_word_analysis)
            morpheme_gloss_ids.append(mg_word_analysis)
            syntactic_category_string.append(''.join(sc_word_analysis))
        syntactic_category_string = u' '.join(syntactic_category_string)
        break_gloss_category = get_break_gloss_category(morpheme_delimiters, morpheme_break,
                                                   morpheme_gloss, syntactic_category_string, bgc_delimiter)
    else:
        morpheme_break_ids = morpheme_gloss_ids = syntactic_category_string = break_gloss_category = None
    return (unicode(json.dumps(morpheme_break_ids)), unicode(json.dumps(morpheme_gloss_ids)),
           syntactic_category_string, break_gloss_category, matches_found)



################################################################################
# Form -> Morpheme updating functionality
################################################################################

def update_forms_containing_this_form_as_morpheme(form, change='create', previous_version=None):
    """Update the morphological analysis-related attributes of every form containing the input form as morpheme.
    
    Update the values of the ``morpheme_break_ids``, ``morpheme_gloss_ids``,
    ``syntactic_category_string``, and ``break_gloss_category`` attributes of each
    form that contains the input form in its morphological analysis, i.e., each
    form whose ``morpheme_break`` value contains the input form's
    ``morpheme_break`` value as a morpheme or whose ``morpheme_gloss`` value
    contains the input form's ``morpheme_gloss`` line as a gloss.  If the input
    form is not lexical (i.e., if it contains the space character or a
    morpheme delimiter), then no updates occur.

    :param form: a form model object.
    :param str change: indicates whether the form has just been deleted or created/updated.
    :param dict previous_version: a representation of the form prior to update.
    :returns: ``None``

    """

    if h.is_lexical(form):
        # Here we construct the query to get all forms that may have been affected
        # by the change to the lexical item (i.e., form).
        morpheme_delimiters = h.get_morpheme_delimiters()
        escaped_morpheme_delimiters = [h.esc_RE_meta_chars(d) for d in morpheme_delimiters]
        start_patt = '(%s)' % '|'.join(escaped_morpheme_delimiters + [u' ', '^'])
        end_patt = '(%s)' % '|'.join(escaped_morpheme_delimiters + [u' ', '$'])
        morpheme_patt = '%s%s%s' % (start_patt, form.morpheme_break, end_patt)
        gloss_patt = '%s%s%s' % (start_patt, form.morpheme_gloss, end_patt)
        disjunctive_conditions = [Form.morpheme_break.op('regexp')(morpheme_patt),
                                 Form.morpheme_gloss.op('regexp')(gloss_patt)]
        matches_query = Session.query(Form).options(subqueryload(Form.syntactic_category))

        # Updates entail a wider range of possibly affected forms
        if previous_version and h.is_lexical(previous_version):
            if previous_version['morpheme_break'] != form.morpheme_break:
                morpheme_patt_PV = '%s%s%s' % (start_patt, previous_version['morpheme_break'], end_patt)
                disjunctive_conditions.append(Form.morpheme_break.op('regexp')(morpheme_patt_PV))
            if previous_version['morpheme_gloss'] != form.morpheme_gloss:
                gloss_patt_PV = '%s%s%s' % (start_patt, previous_version['morpheme_gloss'], end_patt)
                disjunctive_conditions.append(Form.morpheme_gloss.op('regexp')(gloss_patt_PV))

        matches_query = matches_query.filter(or_(*disjunctive_conditions))
        #matches = [f for f in matches_query.all() if f.id != form.id]
        matches = matches_query.all()

        if change == 'delete':
            updated_form_ids = update_morpheme_references_of_forms(matches,
                                morpheme_delimiters, deleted_lexical_items=[form])
        else:
            updated_form_ids = update_morpheme_references_of_forms(matches,
                                morpheme_delimiters, lexical_items=[form])

def update_has_changed_the_analysis(form, form_dict):
    """Return ``True`` if the update from form_dict to form has changed the morphological analysis of the form."""
    try:
        old_syntactic_category_name = form_dict['syntactic_category'].get('name')
    except AttributeError:
        old_syntactic_category_name = None
    return form.morpheme_break != form_dict['morpheme_break'] or \
           form.morpheme_gloss != form_dict['morpheme_gloss'] or \
           form.break_gloss_category != form_dict['break_gloss_category'] or \
           getattr(form.syntactic_category, 'name', None) != old_syntactic_category_name


def update_collections_referencing_this_form(form):
    """Update all collections that reference the input form in their ``contents`` value.

    When a form is deleted, it is necessary to update all collections whose
    ``contents`` value references the deleted form.  The update removes the
    reference, recomputes the ``contents_unpacked``, ``html`` and ``forms``
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
    pattern = unicode(h.form_reference_pattern.pattern.replace('[0-9]+', str(form.id)))
    collections_referencing_this_form = Session.query(Collection).\
        filter(Collection.contents.op('regexp')(pattern)).all()
    for collection in collections_referencing_this_form:
        update_collection_by_deletion_of_referenced_form(collection, form)
