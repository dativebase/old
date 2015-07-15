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

"""Contains the :class:`FilesController` and its auxiliary functions.

.. module:: files
   :synopsis: Contains the files controller and its auxiliary functions.

"""

import logging
import datetime
import os, shutil
import simplejson as json
from string import letters, digits
from random import sample
from paste.fileapp import FileApp
from pylons import request, response, session, config
from pylons.controllers.util import forward
from formencode.validators import Invalid
from sqlalchemy.orm import subqueryload
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import FileCreateWithBase64EncodedFiledataSchema, \
    FileCreateWithFiledataSchema, FileSubintervalReferencingSchema, \
    FileExternallyHostedSchema, FileUpdateSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import File
from onlinelinguisticdatabase.lib.resize import save_reduced_copy

log = logging.getLogger(__name__)

class FilesController(BaseController):
    """Generate responses to requests on file resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('File', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of file resources matching the input JSON query.

        :URL: ``SEARCH /files`` (or ``POST /files/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        """
        try:
            json_search_params = unicode(request.body, request.charset)
            python_search_params = json.loads(json_search_params)
            SQLAQuery = h.eagerload_file(
                self.query_builder.get_SQLA_query(python_search_params.get('query')))
            query = h.filter_restricted_models('File', SQLAQuery)
            return h.add_pagination(query, python_search_params.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except:
            response.status_int = 400
            return {'error': u'The specified search parameters generated an invalid database query'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """Return the data necessary to search the file resources.

        :URL: ``GET /files/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all file resources.

        :URL: ``GET /files`` with optional query string parameters for ordering
            and pagination.
        :returns: a list of all file resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_file(Session.query(File))
            query = h.add_order_by(query, dict(request.GET), self.query_builder)
            query = h.filter_restricted_models('File', query)
            return h.add_pagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """Create a new file resource and return it.

        :URL: ``POST /files``
        :request body: JSON object *or* conventional POST parameters containing
            the attribute values of the new file.
        :content type: ``application/json`` *or* ``multipart/form-data``.
        :returns: the newly created file.

        .. note::
        
            There are three types of file and four types of file creation
            request.

            1. **Local file with** ``multipart/form-data`` **content type.**
               File data are in the request body and the file metadata are
               structured as conventional POST parameters.

            2. **Local file with** ``application/json`` **content type.**
               File data are Base64-encoded and are contained in the same JSON
               object as the metadata, in the request body.

            3. **Subinterval-referencing file with** ``application/json`` **content type.**
               All parameters provided in a JSON object.  No file data are
               present; the ``id`` value of an existing *audio/video* parent
               file must be provided in the ``parent_file`` attribute; values for
               ``start`` and ``end`` attributes are also required.

            4. **Externally hosted file with** ``application/json`` **content-type.**
               All parameters provided in a JSON object.  No file data are
               present; the value of the ``url`` attribute is a valid URL where
               the file data are being served.

        """
        try:
            if request.content_type == 'application/json':
                if len(request.body) > 20971520:    # JSON/Base64 file upload caps out at ~20MB
                    response.status_int = 400
                    return {'error':
                        u'The request body is too large; use the multipart/form-data Content-Type when uploading files greater than 20MB.'}
                values = json.loads(unicode(request.body, request.charset))
                if 'base64_encoded_file' in values:
                    file = create_base64_file(values)
                elif 'url' in values:
                    file = create_externally_hosted_file(values)
                else:
                    file = create_subinterval_referencing_file(values)
            else:
                file = create_plain_file()
            file.lossy_filename = save_reduced_copy(file, config)
            Session.add(file)
            Session.commit()
            return file
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except InvalidFieldStorageObjectError:
            response.status_int = 400
            return {'error': 'The attempted multipart/form-data file upload failed.'}
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """Return the data necessary to create a new file.

        :URL: ``GET /files/new`` with optional query string parameters 
        :returns: a dictionary of lists of resources.

        .. note::
        
           See :func:`get_new_edit_file_data` to understand how the query string
           parameters can affect the contents of the lists in the returned
           dictionary.

        """
        return get_new_edit_file_data(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a file and return it.
        
        :URL: ``PUT /files/id``
        :Request body: JSON object representing the file with updated attribute values.
        :param str id: the ``id`` value of the file to be updated.
        :returns: the updated file model.

        """
        file = h.eagerload_file(Session.query(File)).get(int(id))
        if file:
            unrestricted_users = h.get_unrestricted_users()
            user = session['user']
            if h.user_is_authorized_to_access_model(user, file, unrestricted_users):
                try:
                    if getattr(file, 'parent_file', None):
                        file = update_subinterval_referencing_file(file)
                    elif getattr(file, 'url', None):
                        file = update_externally_hosted_file(file)
                    else:
                        file = update_file(file)
                    # file will be False if there are no changes
                    if file:
                        Session.add(file)
                        Session.commit()
                        return file
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
            return {'error': 'There is no file with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing file and return it.

        :URL: ``DELETE /files/id``
        :param str id: the ``id`` value of the file to be deleted.
        :returns: the deleted file model.

        .. note::

           Only administrators and a file's enterer can delete it.

        """
        file = h.eagerload_file(Session.query(File)).get(id)
        if file:
            if session['user'].role == u'administrator' or \
            file.enterer is session['user']:
                delete_file(file)
                return file
            else:
                response.status_int = 403
                return h.unauthorized_msg
        else:
            response.status_int = 404
            return {'error': 'There is no file with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a file.

        :URL: ``GET /files/id``
        :param str id: the ``id`` value of the file to be returned.
        :returns: a file model object.

        """
        file = h.eagerload_file(Session.query(File)).get(id)
        if file:
            unrestricted_users = h.get_unrestricted_users()
            user = session['user']
            if h.user_is_authorized_to_access_model(user, file, unrestricted_users):
                return file
            else:
                response.status_int = 403
                return h.unauthorized_msg
        else:
            response.status_int = 404
            return {'error': 'There is no file with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a file and the data needed to update it.

        :URL: ``GET /files/edit`` with optional query string parameters 
        :param str id: the ``id`` value of the file that will be updated.
        :returns: a dictionary of the form::

                {"file": {...}, "data": {...}}

            where the value of the ``file`` key is a dictionary representation
            of the file and the value of the ``data`` key is a dictionary
            containing the objects necessary to update a file, viz. the return
            value of :func:`FilesController.new`

        .. note::
        
           This action can be thought of as a combination of
           :func:`FilesController.show` and :func:`FilesController.new`.  See
           :func:`get_new_edit_file_data` to understand how the query string
           parameters can affect the contents of the lists in the ``data``
           dictionary.

        """
        response.content_type = 'application/json'
        file = h.eagerload_file(Session.query(File)).get(id)
        if file:
            unrestricted_users = h.get_unrestricted_users()
            if h.user_is_authorized_to_access_model(session['user'], file, unrestricted_users):
                return {'data': get_new_edit_file_data(request.GET), 'file': file}
            else:
                response.status_int = 403
                return h.unauthorized_msg
        else:
            response.status_int = 404
            return {'error': 'There is no file with id %s' % id}

    @h.restrict('GET')
    @h.authenticate_with_JSON
    def serve(self, id):
        """Return the file data (binary stream) of the file.
        
        :param str id: the ``id`` value of the file whose file data are requested.

        """
        return serve_file(id)

    @h.restrict('GET')
    @h.authenticate_with_JSON
    def serve_reduced(self, id):
        """Return the reduced-size file data (binary stream) of the file.
        
        :param str id: the ``id`` value of the file whose reduced-size file data
            are requested.

        """
        return serve_file(id, True)


def serve_file(id, reduced=False):
    """Serve the content (binary data) of a file.
    
    :param str id: the ``id`` value of the file whose file data will be served.
    :param bool reduced: toggles serving of file data or reduced-size file data.

    """
    file = Session.query(File).options(subqueryload(File.parent_file)).get(id)
    if getattr(file, 'parent_file', None):
        file = file.parent_file
    elif getattr(file, 'url', None):
        response.status_int = 400
        return json.dumps({'error': u'The content of file %s is stored elsewhere at %s' % (id, file.url)})
    if file:
        files_dir = h.get_OLD_directory_path('files', config=config)
        if reduced:
            filename = getattr(file, 'lossy_filename', None)
            if not filename:
                response.status_int = 404
                return json.dumps({'error': u'There is no size-reduced copy of file %s' % id})
            file_path = os.path.join(files_dir, 'reduced_files', filename)
        else:
            file_path = os.path.join(files_dir, file.filename)
        unrestricted_users = h.get_unrestricted_users()
        if h.user_is_authorized_to_access_model(session['user'], file, unrestricted_users):
            return forward(FileApp(file_path))
        else:
            response.status_int = 403
            return json.dumps(h.unauthorized_msg)
    else:
        response.status_int = 404
        return json.dumps({'error': 'There is no file with id %s' % id})

################################################################################
# File Create Functionality
################################################################################

def get_unique_file_path(file_path):
    """Get a unique file path.
    
    :param str file_path: an absolute file path.
    :returns: a tuple whose first element is the open file object and whose
        second is the unique file path as a unicode string.

    """
    file_path_parts = os.path.splitext(file_path) # returns ('/path/file', '.ext')
    while 1:
        try:
            file_descriptor = os.open(file_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            return os.fdopen(file_descriptor, 'wb'), unicode(file_path)
        except (OSError, IOError):
            pass
        file_path = u'%s_%s%s' % (file_path_parts[0][:230],
                    ''.join(sample(digits + letters, 8)), file_path_parts[1])

def add_standard_metadata(file, data):
    """Add the standard metadata to the file model using the data dictionary.
    
    :param file: file model object
    :param dict data: dictionary containing file attribute values.
    :returns: the updated file model object.
    
    """
    file.description = h.normalize(data['description'])
    file.utterance_type = data['utterance_type']
    file.date_elicited = data['date_elicited']
    if data['elicitor']:
        file.elicitor = data['elicitor']
    if data['speaker']:
        file.speaker = data['speaker']
    file.tags = [t for t in data['tags'] if t]
    file.forms = [f for f in data['forms'] if f]
    now = h.now()
    file.datetime_entered = now
    file.datetime_modified = now
    # Because of SQLAlchemy's uniqueness constraints, we may need to set the
    # enterer to the elicitor.
    if data['elicitor'] and (data['elicitor'].id == session['user'].id):
        file.enterer = data['elicitor']
    else:
        file.enterer = session['user']
    return file

def restrict_file_by_forms(file):
    """Restrict the entire file if it is associated to restricted forms.
    
    :param file: a file model object.
    :returns: the file model object potentially tagged as "restricted".

    """
    tags = [f.tags for f in file.forms]
    tags = [tag for tag_list in tags for tag in tag_list]
    restricted_tags = [tag for tag in tags if tag.name == u'restricted']
    if restricted_tags:
        restricted_tag = restricted_tags[0]
        if restricted_tag not in file.tags:
            file.tags.append(restricted_tag)
    return file

class InvalidFieldStorageObjectError(Exception):
    pass

def create_base64_file(data):
    """Create a local file using data from a ``Content-Type: application/json`` request.

    :param dict data: the data to create the file model.
    :param str data['base64_encoded_file']: Base64-encoded file data.
    :returns: an SQLAlchemy model object representing the file.

    """

    data['MIME_type'] = u''  # during validation, the schema will set a proper value based on the base64_encoded_file or filename attribute
    schema = FileCreateWithBase64EncodedFiledataSchema()
    state = h.State()
    state.full_dict = data
    state.user = session['user']
    data = schema.to_python(data, state)

    file = File()
    file.MIME_type = data['MIME_type']
    file.filename = h.normalize(data['filename'])

    file = add_standard_metadata(file, data)

    # Write the file to disk (making sure it's unique and thereby potentially)
    # modifying file.filename; and calculate file.size.
    file_data = data['base64_encoded_file']     # base64-decoded during validation
    files_path = h.get_OLD_directory_path('files', config=config)
    file_path = os.path.join(files_path, file.filename)
    file_object, file_path = get_unique_file_path(file_path)
    file.filename = os.path.split(file_path)[-1]
    file.name = file.filename
    file_object.write(file_data)
    file_object.close()
    file_data = None
    file.size = os.path.getsize(file_path)

    file = restrict_file_by_forms(file)
    return file

def create_externally_hosted_file(data):
    """Create an externally hosted file.

    :param dict data: the data to create the file model.
    :param str data['url']: a valid URL where the file data are served.
    :returns: an SQLAlchemy model object representing the file.

    Optional keys of the data dictionary, not including the standard metadata
    ones, are ``name``, ``password`` and ``MIME_type``.
    
    """
    data['password'] = data.get('password') or u''
    schema = FileExternallyHostedSchema()
    data = schema.to_python(data)
    file = File()

    # User-inputted string data
    file.name = h.normalize(data['name'])
    file.password = data['password']
    file.MIME_type = data['MIME_type']
    file.url = data['url']

    file = add_standard_metadata(file, data)
    file = restrict_file_by_forms(file)
    return file

def create_subinterval_referencing_file(data):
    """Create a subinterval-referencing file.

    :param dict data: the data to create the file model.
    :param int data['parent_file']: the ``id`` value of an audio/video file model.
    :param float/int data['start']: the start of the interval in seconds.
    :param float/int data['end']: the end of the interval in seconds.
    :returns: an SQLAlchemy model object representing the file.

    A value for ``data['name']`` may also be supplied.

    """
    data['name'] = data.get('name') or u''
    schema = FileSubintervalReferencingSchema()
    state = h.State()
    state.full_dict = data
    state.user = session['user']
    data = schema.to_python(data, state)

    file = File()

    # Data unique to referencing subinterval files
    file.parent_file = data['parent_file']
    file.name = h.normalize(data['name']) or file.parent_file.filename   # Name defaults to the parent file's filename if nothing provided by user
    file.start = data['start']
    file.end = data['end']
    file.MIME_type = file.parent_file.MIME_type

    file = add_standard_metadata(file, data)
    file = restrict_file_by_forms(file)

    return file

def create_plain_file():
    """Create a local file using data from a ``Content-Type: multipart/form-data`` request.

    :param request.POST['filedata']: a ``cgi.FieldStorage`` object containing
        the file data.
    :param str request.POST['filename']: the name of the binary file.
    :returns: an SQLAlchemy model object representing the file.

    .. note::
    
        The validator expects ``request.POST`` to encode list input via the
        ``formencode.variabledecode.NestedVariables`` format.  E.g., a list of
        form ``id`` values would be provided as values to keys with names like
        ``'forms-0'``, ``'forms-1'``, ``'forms-2'``, etc.

    """
    values = dict(request.params)
    filedata = request.POST.get('filedata')
    if not hasattr(filedata, 'file'):
        raise InvalidFieldStorageObjectError
    if not values.get('filename'):
        values['filename'] = os.path.split(filedata.filename)[-1]
    values['filedata_first_KB'] = filedata.value[:1024]
    schema = FileCreateWithFiledataSchema()
    data = schema.to_python(values)

    file = File()
    file.filename = h.normalize(data['filename'])
    file.MIME_type = data['MIME_type']

    files_path = h.get_OLD_directory_path('files', config=config)
    file_path = os.path.join(files_path, file.filename)
    file_object, file_path = get_unique_file_path(file_path)
    file.filename = os.path.split(file_path)[-1]
    file.name = file.filename
    shutil.copyfileobj(filedata.file, file_object)
    filedata.file.close()
    file_object.close()
    file.size = os.path.getsize(file_path)

    file = add_standard_metadata(file, data)

    return file

################################################################################
# File Update Functionality
################################################################################

def update_standard_metadata(file, data, changed):
    """Update the standard metadata attributes of the input file.
    
    :param file: a file model object to be updated.
    :param dict data: the data used to update the file model.
    :param bool changed: indicates whether the file has been changed.
    :returns: a tuple whose first element is the file model and whose second is
        the boolean ``changed``.

    """
    changed = file.set_attr('description', h.normalize(data['description']), changed)
    changed = file.set_attr('utterance_type', h.normalize(data['utterance_type']), changed)
    changed = file.set_attr('date_elicited', data['date_elicited'], changed)
    changed = file.set_attr('elicitor', data['elicitor'], changed)
    changed = file.set_attr('speaker', data['speaker'], changed)

    # Many-to-Many Data: tags & forms
    # Update only if the user has made changes.
    forms_to_add = [f for f in data['forms'] if f]
    tags_to_add = [t for t in data['tags'] if t]

    if set(forms_to_add) != set(file.forms):
        file.forms = forms_to_add
        changed = True

        # Cause the entire file to be tagged as restricted if any one of its
        # forms are so tagged.
        tags = [f.tags for f in file.forms]
        tags = [tag for tag_list in tags for tag in tag_list]
        restricted_tags = [tag for tag in tags if tag.name == u'restricted']
        if restricted_tags:
            restricted_tag = restricted_tags[0]
            if restricted_tag not in tags_to_add:
                tags_to_add.append(restricted_tag)

    if set(tags_to_add) != set(file.tags):
        file.tags = tags_to_add
        changed = True

    return file, changed

def update_file(file):
    """Update a local file model.
    
    :param file: a file model object to update.
    :param request.body: a JSON object containing the data for updating the file.
    :returns: the file model or, if the file has not been updated, ``False``.

    """
    changed = False
    schema = FileUpdateSchema()
    data = json.loads(unicode(request.body, request.charset))
    state = h.State()
    state.full_dict = data
    state.user = session['user']
    data = schema.to_python(data, state)
    file, changed = update_standard_metadata(file, data, changed)
    if changed:
        file.datetime_modified = datetime.datetime.utcnow()
        return file
    return changed

def update_subinterval_referencing_file(file):
    """Update a subinterval-referencing file model.

    :param file: a file model object to update.
    :param request.body: a JSON object containing the data for updating the file.
    :returns: the file model or, if the file has not been updated, ``False``.

    """
    changed = False
    schema = FileSubintervalReferencingSchema()
    data = json.loads(unicode(request.body, request.charset))
    data['name'] = data.get('name') or u''
    state = h.State()
    state.full_dict = data
    state.user = session['user']
    data = schema.to_python(data, state)

    # Data unique to referencing subinterval files
    changed = file.set_attr('parent_file', data['parent_file'], changed)
    changed = file.set_attr('name', (h.normalize(data['name']) or file.parent_file.filename), changed)
    changed = file.set_attr('start', data['start'], changed)
    changed = file.set_attr('end', data['end'], changed)

    file, changed = update_standard_metadata(file, data, changed)

    if changed:
        file.datetime_modified = datetime.datetime.utcnow()
        return file
    return changed

def update_externally_hosted_file(file):
    """Update an externally hosted file model.

    :param file: a file model object to update.
    :param request.body: a JSON object containing the data for updating the file.
    :returns: the file model or, if the file has not been updated, ``False``.

    """
    changed = False
    data = json.loads(unicode(request.body, request.charset))
    data['password'] = data.get('password') or u''
    data = FileExternallyHostedSchema().to_python(data)

    # Data unique to referencing subinterval files
    changed = file.set_attr('url', data['url'], changed)
    changed = file.set_attr('name', h.normalize(data['name']), changed)
    changed = file.set_attr('password', data['password'], changed)
    changed = file.set_attr('MIME_type', data['MIME_type'], changed)

    file, changed = update_standard_metadata(file, data, changed)

    if changed:
        file.datetime_modified = datetime.datetime.utcnow()
        return file
    return changed


################################################################################
# Delete File Functionality
################################################################################

def delete_file(file):
    """Delete a file model.

    :param file: a file model object to delete.
    :returns: ``None``.

    This deletes the file model object from the database as well as any binary
    files associated with it that are stored on the filesystem.

    """
    if getattr(file, 'filename', None):
        file_path = os.path.join(h.get_OLD_directory_path('files', config=config),
                                file.filename)
        os.remove(file_path)
    if getattr(file, 'lossy_filename', None):
        file_path = os.path.join(h.get_OLD_directory_path('reduced_files', config=config),
                                file.lossy_filename)
        os.remove(file_path)
    Session.delete(file)
    Session.commit()


################################################################################
# New/Edit File Functionality
################################################################################

def get_new_edit_file_data(GET_params):
    """Return the data necessary to create a new OLD file or update an existing one.
    
    :param GET_params: the ``request.GET`` dictionary-like object generated by
        Pylons which contains the query string parameters of the request.
    :returns: A dictionary whose values are lists of objects needed to create or
        update files.

    If ``GET_params`` has no keys, then return all relevant data lists.  If
    ``GET_params`` does have keys, then for each key whose value is a non-empty
    string (and not a valid ISO 8601 datetime) add the appropriate list of
    objects to the return dictionary.  If the value of a key is a valid ISO 8601
    datetime string, add the corresponding list of objects *only* if the
    datetime does *not* match the most recent ``datetime_modified`` value of the
    resource.  That is, a non-matching datetime indicates that the requester has
    out-of-date data.

    """
    # Map param names to the OLD model objects from which they are derived.
    param_name2model_name = {
        'tags': 'Tag',
        'speakers': 'Speaker',
        'users': 'User'
    }

    # map_ maps param names to functions that retrieve the appropriate data
    # from the db.
    map_ = {
        'tags': h.get_mini_dicts_getter('Tag'),
        'speakers': h.get_mini_dicts_getter('Speaker'),
        'users': h.get_mini_dicts_getter('User')
    }

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in map_])
    result['utterance_types'] = h.utterance_types
    result['allowed_file_types'] = h.allowed_file_types

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
                    if val_as_datetime_obj != h.get_most_recent_modification_datetime(
                    param_name2model_name[key]):
                        result[key] = map_[key]()
                else:
                    result[key] = map_[key]()

    # There are no GET params, so we get everything from the db and return it.
    else:
        for key in map_:
            result[key] = map_[key]()

    return result
