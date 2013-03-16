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
import re
import os, shutil
from cgi import FieldStorage
import simplejson as json
from string import letters, digits
from random import sample
from paste.fileapp import FileApp
from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from pylons.decorators import jsonify
from pylons.controllers.util import forward
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc
from sqlalchemy.orm import subqueryload
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import FileCreateWithBase64EncodedFiledataSchema, \
    FileCreateWithFiledataSchema, FileSubintervalReferencingSchema, \
    FileExternallyHostedSchema, FileUpdateSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session, Model
from onlinelinguisticdatabase.model import File, User
from onlinelinguisticdatabase.lib.resize import saveReducedCopy

log = logging.getLogger(__name__)

class FilesController(BaseController):
    """Generate responses to requests on file resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder('File', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of file resources matching the input JSON query.

        :URL: ``SEARCH /files`` (or ``POST /files/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "orderBy": [ ... ]},
                 "paginator": { ... }}

            where the ``orderBy`` and ``paginator`` attributes are optional.

        """
        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            SQLAQuery = h.eagerloadFile(
                self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query')))
            query = h.filterRestrictedModels('File', SQLAQuery)
            return h.addPagination(query, pythonSearchParams.get('paginator'))
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
        :returns: ``{"searchParameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all file resources.

        :URL: ``GET /files`` with optional query string parameters for ordering
            and pagination.
        :returns: a list of all file resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerloadFile(Session.query(File))
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels('File', query)
            return h.addPagination(query, dict(request.GET))
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
               file must be provided in the ``parentFile`` attribute; values for
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
                if 'base64EncodedFile' in values:
                    file = createBase64File(values)
                elif 'url' in values:
                    file = createExternallyHostedFile(values)
                else:
                    file = createSubintervalReferencingFile(values)
            else:
                file = createPlainFile()
            file.lossyFilename = saveReducedCopy(file, config)
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
        
           See :func:`getNewEditFileData` to understand how the query string
           parameters can affect the contents of the lists in the returned
           dictionary.

        """
        return getNewEditFileData(request.GET)

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
        file = h.eagerloadFile(Session.query(File)).get(int(id))
        if file:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, file, unrestrictedUsers):
                try:
                    if getattr(file, 'parentFile', None):
                        file = updateSubintervalReferencingFile(file)
                    elif getattr(file, 'url', None):
                        file = updateExternallyHostedFile(file)
                    else:
                        file = updateFile(file)
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
                return h.unauthorizedMsg
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
        file = h.eagerloadFile(Session.query(File)).get(id)
        if file:
            if session['user'].role == u'administrator' or \
            file.enterer is session['user']:
                deleteFile(file)
                return file
            else:
                response.status_int = 403
                return h.unauthorizedMsg
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
        file = h.eagerloadFile(Session.query(File)).get(id)
        if file:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, file, unrestrictedUsers):
                return file
            else:
                response.status_int = 403
                return h.unauthorizedMsg
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
           :func:`getNewEditFileData` to understand how the query string
           parameters can affect the contents of the lists in the ``data``
           dictionary.

        """
        response.content_type = 'application/json'
        file = h.eagerloadFile(Session.query(File)).get(id)
        if file:
            unrestrictedUsers = h.getUnrestrictedUsers()
            if h.userIsAuthorizedToAccessModel(session['user'], file, unrestrictedUsers):
                return {'data': getNewEditFileData(request.GET), 'file': file}
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no file with id %s' % id}

    @h.restrict('GET')
    @h.authenticateWithJSON
    def serve(self, id):
        """Return the file data (binary stream) of the file.
        
        :param str id: the ``id`` value of the file whose file data are requested.

        """
        return serveFile(id)

    @h.restrict('GET')
    @h.authenticateWithJSON
    def serve_reduced(self, id):
        """Return the reduced-size file data (binary stream) of the file.
        
        :param str id: the ``id`` value of the file whose reduced-size file data
            are requested.

        """
        return serveFile(id, True)


def serveFile(id, reduced=False):
    """Serve the content (binary data) of a file.
    
    :param str id: the ``id`` value of the file whose file data will be served.
    :param bool reduced: toggles serving of file data or reduced-size file data.

    """
    file = Session.query(File).options(subqueryload(File.parentFile)).get(id)
    if getattr(file, 'parentFile', None):
        file = file.parentFile
    elif getattr(file, 'url', None):
        response.status_int = 400
        return json.dumps({'error': u'The content of file %s is stored elsewhere at %s' % (id, file.url)})
    if file:
        filesDir = h.getOLDDirectoryPath('files', config=config)
        if reduced:
            filename = getattr(file, 'lossyFilename', None)
            if not filename:
                response.status_int = 404
                return json.dumps({'error': u'There is no size-reduced copy of file %s' % id})
            filePath = os.path.join(filesDir, 'reduced_files', filename)
        else:
            filePath = os.path.join(filesDir, file.filename)
        unrestrictedUsers = h.getUnrestrictedUsers()
        if h.userIsAuthorizedToAccessModel(session['user'], file, unrestrictedUsers):
            return forward(FileApp(filePath))
        else:
            response.status_int = 403
            return json.dumps(h.unauthorizedMsg)
    else:
        response.status_int = 404
        return json.dumps({'error': 'There is no file with id %s' % id})

################################################################################
# File Create Functionality
################################################################################

def getUniqueFilePath(filePath):
    """Get a unique file path.
    
    :param str filePath: an absolute file path.
    :returns: a tuple whose first element is the open file object and whose
        second is the unique file path as a unicode string.

    """
    filePathParts = os.path.splitext(filePath) # returns ('/path/file', '.ext')
    while 1:
        try:
            fileDescriptor = os.open(filePath, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            return os.fdopen(fileDescriptor, 'wb'), unicode(filePath)
        except (OSError, IOError):
            pass
        filePath = u'%s_%s%s' % (filePathParts[0][:230],
                    ''.join(sample(digits + letters, 8)), filePathParts[1])

def addStandardMetadata(file, data):
    """Add the standard metadata to the file model using the data dictionary.
    
    :param file: file model object
    :param dict data: dictionary containing file attribute values.
    :returns: the updated file model object.
    
    """
    file.description = h.normalize(data['description'])
    file.utteranceType = data['utteranceType']
    file.dateElicited = data['dateElicited']
    if data['elicitor']:
        file.elicitor = data['elicitor']
    if data['speaker']:
        file.speaker = data['speaker']
    file.tags = [t for t in data['tags'] if t]
    file.forms = [f for f in data['forms'] if f]
    now = h.now()
    file.datetimeEntered = now
    file.datetimeModified = now
    file.enterer = session['user']
    return file

def restrictFileByForms(file):
    """Restrict the entire file if it is associated to restricted forms.
    
    :param file: a file model object.
    :returns: the file model object potentially tagged as "restricted".

    """
    tags = [f.tags for f in file.forms]
    tags = [tag for tagList in tags for tag in tagList]
    restrictedTags = [tag for tag in tags if tag.name == u'restricted']
    if restrictedTags:
        restrictedTag = restrictedTags[0]
        if restrictedTag not in file.tags:
            file.tags.append(restrictedTag)
    return file

class InvalidFieldStorageObjectError(Exception):
    pass

def createBase64File(data):
    """Create a local file using data from a ``Content-Type: application/json`` request.

    :param dict data: the data to create the file model.
    :param str data['base64EncodedFile']: Base64-encoded file data.
    :returns: an SQLAlchemy model object representing the file.

    """

    data['MIMEtype'] = u''  # during validation, the schema will set a proper value based on the base64EncodedFile or filename attribute
    schema = FileCreateWithBase64EncodedFiledataSchema()
    state = h.State()
    state.full_dict = data
    state.user = session['user']
    data = schema.to_python(data, state)

    file = File()
    file.MIMEtype = data['MIMEtype']
    file.filename = h.normalize(data['filename'])

    file = addStandardMetadata(file, data)

    # Write the file to disk (making sure it's unique and thereby potentially)
    # modifying file.filename; and calculate file.size.
    fileData = data['base64EncodedFile']     # base64-decoded during validation
    filesPath = h.getOLDDirectoryPath('files', config=config)
    filePath = os.path.join(filesPath, file.filename)
    fileObject, filePath = getUniqueFilePath(filePath)
    file.filename = os.path.split(filePath)[-1]
    file.name = file.filename
    fileObject.write(fileData)
    fileObject.close()
    fileData = None
    file.size = os.path.getsize(filePath)

    file = restrictFileByForms(file)
    return file

def createExternallyHostedFile(data):
    """Create an externally hosted file.

    :param dict data: the data to create the file model.
    :param str data['url']: a valid URL where the file data are served.
    :returns: an SQLAlchemy model object representing the file.

    Optional keys of the data dictionary, not including the standard metadata
    ones, are ``name``, ``password`` and ``MIMEtype``.
    
    """
    data['password'] = data.get('password') or u''
    schema = FileExternallyHostedSchema()
    data = schema.to_python(data)
    file = File()

    # User-inputted string data
    file.name = h.normalize(data['name'])
    file.password = data['password']
    file.MIMEtype = data['MIMEtype']
    file.url = data['url']

    file = addStandardMetadata(file, data)
    file = restrictFileByForms(file)
    return file

def createSubintervalReferencingFile(data):
    """Create a subinterval-referencing file.

    :param dict data: the data to create the file model.
    :param int data['parentFile']: the ``id`` value of an audio/video file model.
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
    file.parentFile = data['parentFile']
    file.name = h.normalize(data['name']) or file.parentFile.filename   # Name defaults to the parent file's filename if nothing provided by user
    file.start = data['start']
    file.end = data['end']
    file.MIMEtype = file.parentFile.MIMEtype

    file = addStandardMetadata(file, data)
    file = restrictFileByForms(file)

    return file

def createPlainFile():
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
    values['filedataFirstKB'] = filedata.value[:1024]
    schema = FileCreateWithFiledataSchema()
    data = schema.to_python(values)

    file = File()
    file.filename = h.normalize(data['filename'])
    file.MIMEtype = data['MIMEtype']

    filesPath = h.getOLDDirectoryPath('files', config=config)
    filePath = os.path.join(filesPath, file.filename)
    fileObject, filePath = getUniqueFilePath(filePath)
    file.filename = os.path.split(filePath)[-1]
    file.name = file.filename
    shutil.copyfileobj(filedata.file, fileObject)
    filedata.file.close()
    fileObject.close()
    file.size = os.path.getsize(filePath)

    file = addStandardMetadata(file, data)

    return file

################################################################################
# File Update Functionality
################################################################################

def updateStandardMetadata(file, data, changed):
    """Update the standard metadata attributes of the input file.
    
    :param file: a file model object to be updated.
    :param dict data: the data used to update the file model.
    :param bool changed: indicates whether the file has been changed.
    :returns: a tuple whose first element is the file model and whose second is
        the boolean ``changed``.

    """
    changed = h.setAttr(file, 'description', h.normalize(data['description']), changed)
    changed = h.setAttr(file, 'utteranceType', h.normalize(data['utteranceType']), changed)
    changed = h.setAttr(file, 'dateElicited', data['dateElicited'], changed)
    changed = h.setAttr(file, 'elicitor', data['elicitor'], changed)
    changed = h.setAttr(file, 'speaker', data['speaker'], changed)

    # Many-to-Many Data: tags & forms
    # Update only if the user has made changes.
    formsToAdd = [f for f in data['forms'] if f]
    tagsToAdd = [t for t in data['tags'] if t]

    if set(formsToAdd) != set(file.forms):
        file.forms = formsToAdd
        changed = True

        # Cause the entire file to be tagged as restricted if any one of its
        # forms are so tagged.
        tags = [f.tags for f in file.forms]
        tags = [tag for tagList in tags for tag in tagList]
        restrictedTags = [tag for tag in tags if tag.name == u'restricted']
        if restrictedTags:
            restrictedTag = restrictedTags[0]
            if restrictedTag not in tagsToAdd:
                tagsToAdd.append(restrictedTag)

    if set(tagsToAdd) != set(file.tags):
        file.tags = tagsToAdd
        changed = True

    return file, changed

def updateFile(file):
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
    file, changed = updateStandardMetadata(file, data, changed)
    if changed:
        file.datetimeModified = datetime.datetime.utcnow()
        return file
    return changed

def updateSubintervalReferencingFile(file):
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
    changed = h.setAttr(file, 'parentFile', data['parentFile'], changed)
    changed = h.setAttr(file, 'name', (h.normalize(data['name']) or file.parentFile.filename), changed)
    changed = h.setAttr(file, 'start', data['start'], changed)
    changed = h.setAttr(file, 'end', data['end'], changed)

    file, changed = updateStandardMetadata(file, data, changed)

    if changed:
        file.datetimeModified = datetime.datetime.utcnow()
        return file
    return changed

def updateExternallyHostedFile(file):
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
    changed = h.setAttr(file, 'url', data['url'], changed)
    changed = h.setAttr(file, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(file, 'password', data['password'], changed)
    changed = h.setAttr(file, 'MIMEtype', data['MIMEtype'], changed)

    file, changed = updateStandardMetadata(file, data, changed)

    if changed:
        file.datetimeModified = datetime.datetime.utcnow()
        return file
    return changed


################################################################################
# Delete File Functionality
################################################################################

def deleteFile(file):
    """Delete a file model.

    :param file: a file model object to delete.
    :returns: ``None``.

    This deletes the file model object from the database as well as any binary
    files associated with it that are stored on the filesystem.

    """
    if getattr(file, 'filename', None):
        filePath = os.path.join(h.getOLDDirectoryPath('files', config=config),
                                file.filename)
        os.remove(filePath)
    if getattr(file, 'lossyFilename', None):
        filePath = os.path.join(h.getOLDDirectoryPath('reduced_files', config=config),
                                file.lossyFilename)
        os.remove(filePath)
    Session.delete(file)
    Session.commit()


################################################################################
# New/Edit File Functionality
################################################################################

def getNewEditFileData(GET_params):
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
    datetime does *not* match the most recent ``datetimeModified`` value of the
    resource.  That is, a non-matching datetime indicates that the requester has
    out-of-date data.

    """
    # Map param names to the OLD model objects from which they are derived.
    paramName2ModelName = {
        'tags': 'Tag',
        'speakers': 'Speaker',
        'users': 'User'
    }

    # map_ maps param names to functions that retrieve the appropriate data
    # from the db.
    map_ = {
        'tags': h.getMiniDictsGetter('Tag'),
        'speakers': h.getMiniDictsGetter('Speaker'),
        'users': h.getMiniDictsGetter('User')
    }

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in map_])
    result['utteranceTypes'] = h.utteranceTypes
    result['allowedFileTypes'] = h.allowedFileTypes

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
                    if valAsDatetimeObj != h.getMostRecentModificationDatetime(
                    paramName2ModelName[key]):
                        result[key] = map_[key]()
                else:
                    result[key] = map_[key]()

    # There are no GET params, so we get everything from the db and return it.
    else:
        for key in map_:
            result[key] = map_[key]()

    return result
