import logging
import datetime
import re
import os
import simplejson as json
from string import letters, digits
from random import sample
from paste.fileapp import FileApp
from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from pylons.controllers.util import forward
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from old.lib.base import BaseController
from old.lib.schemata import FileCreateSchema, FileUpdateSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import File, User

log = logging.getLogger(__name__)

class FilesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('File')

    @restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """SEARCH /files: Return all files matching the filter passed as JSON in
        the request body.  Note: POST /files/search also routes to this action.
        The request body must be a JSON object with a 'query' attribute; a
        'paginator' attribute is optional.  The 'query' object is passed to the
        getSQLAQuery() method of an SQLAQueryBuilder instance and an SQLA query
        is returned or an error is raised.  The 'query' object requires a
        'filter' attribute; an 'orderBy' attribute is optional.
        """

        response.content_type = 'application/json'
        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            SQLAQuery = self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query'))
            query = h.filterRestrictedModels('File', SQLAQuery)
            result = h.addPagination(query, pythonSearchParams.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return json.dumps({'errors': e.unpack_errors()})
        # SQLAQueryBuilder should have captured these exceptions (and packed
        # them into an OLDSearchParseError) or sidestepped them, but here we'll
        # handle any that got past -- just in case.
        except (OperationalError, AttributeError, InvalidRequestError, RuntimeError):
            response.status_int = 400
            return json.dumps({'error':
                u'The specified search parameters generated an invalid database query'})
        else:
            return json.dumps(result, cls=h.JSONOLDEncoder)

    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /files: Return all files."""
        # url('files')
        response.content_type = 'application/json'
        try:
            query = Session.query(File)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels('File', query)
            result = h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return json.dumps({'errors': e.unpack_errors()})
        else:
            return json.dumps(result, cls=h.JSONOLDEncoder)

    @restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """POST /files: Create a new file."""
        # url('files')
        response.content_type = 'application/json'
        try:
            schema = FileCreateSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.State()
            state.full_dict = values
            state.user = session['user']
            result = schema.to_python(values, state)
        except h.JSONDecodeError:
            response.status_int = 400
            result = h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            result = json.dumps({'errors': e.unpack_errors()})
        else:
            file = createNewFile(result)
            Session.add(file)
            Session.commit()
            result = json.dumps(file, cls=h.JSONOLDEncoder)
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """GET /new_file: Return the data necessary to create a new OLD file.

        Return a JSON object with the following properties: 'tags',
        'utteranceTypes', 'speakers' and 'users', the value of each of which is
        an array that is either empty or contains the appropriate objects.

        See the getNewEditFileData function to understand how the GET params can
        affect the contents of the arrays.
        """

        response.content_type = 'application/json'
        result = getNewEditFileData(request.GET)
        return json.dumps(result, cls=h.JSONOLDEncoder)

    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /files/id: Update an existing file."""

        response.content_type = 'application/json'
        file = Session.query(File).get(int(id))
        if file:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, file, unrestrictedUsers):
                try:
                    schema = FileUpdateSchema()
                    values = json.loads(unicode(request.body, request.charset))
                    state = h.State()
                    state.full_dict = values
                    state.user = user
                    result = schema.to_python(values, state)
                except h.JSONDecodeError:
                    response.status_int = 400
                    result = h.JSONDecodeErrorResponse
                except Invalid, e:
                    response.status_int = 400
                    result = json.dumps({'errors': e.unpack_errors()})
                else:
                    file = updateFile(file, result)
                    # file will be False if there are no changes (cf. updateFile).
                    if file:
                        Session.add(file)
                        Session.commit()
                        result = json.dumps(file, cls=h.JSONOLDEncoder)
                    else:
                        response.status_int = 400
                        result = json.dumps({'error': u''.join([
                            u'The update request failed because the submitted ',
                            u'data were not new.'])})
            else:
                response.status_int = 403
                result = h.unauthorizedJSONMsg
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no file with id %s' % id})
        return result

    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /files/id: Delete an existing file.  Only the enterer and
        administrators can delete a file.
        """

        response.content_type = 'application/json'
        file = Session.query(File).get(id)
        if file:
            if session['user'].role == u'administrator' or \
            file.enterer is session['user']:
                deleteFile(file)
                result = json.dumps(file, cls=h.JSONOLDEncoder)
            else:
                response.status_int = 403
                result = h.unauthorizedJSONMsg
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no file with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /files/id: Return a JSON object representation of the file with
        id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """

        response.content_type = 'application/json'
        file = Session.query(File).get(id)
        if file:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, file, unrestrictedUsers):
                result = json.dumps(file, cls=h.JSONOLDEncoder)
            else:
                response.status_int = 403
                result = h.unauthorizedJSONMsg
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no file with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /files/id/edit: Return the data necessary to update an existing
        OLD file, i.e., the file's properties and the necessary additional data,
        i.e., users, speakers, etc.

        This action can be thought of as a combination of the 'show' and 'new'
        actions.  The output will be a JSON object of the form

            {file: {...}, data: {...}},

        where output.file is an object containing the file's properties (cf. the
        output of show) and output.data is an object containing the data
        required to add a new file (cf. the output of new).

        GET parameters will affect the value of output.data in the same way as
        for the new action, i.e., no params will result in all the necessary
        output.data being retrieved from the db while specified params will
        result in selective retrieval (see getNewEditFileData for details).
        """

        response.content_type = 'application/json'
        file = Session.query(File).get(id)
        if file:
            unrestrictedUsers = h.getUnrestrictedUsers()
            if not h.userIsAuthorizedToAccessModel(
                                    session['user'], file, unrestrictedUsers):
                response.status_int = 403
                result = h.unauthorizedJSONMsg
            else:
                data = getNewEditFileData(request.GET)
                result = {'data': data, 'file': file}
                result = json.dumps(result, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no file with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    def retrieve(self, id):
        """Return the file data (binary stream) for the file in files/ with
        name=id.
        """
        filePath = os.path.join(config['app_conf']['permanent_store'], id)
        app = FileApp(filePath)
        return forward(app)

################################################################################
# File Create & Update Functions
################################################################################

def getNewEditFileData(GET_params):
    """Return the data necessary to create a new OLD file or update an existing
    one.  The GET_params parameter is the request.GET dictionary-like object
    generated by Pylons.

    If no parameters are provided (i.e., GET_params is empty), then retrieve all
    data (i.e., tags, speakers, etc.) from the db and return it.

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
        'tags': 'Tag',
        'speakers': 'Speaker',
        'users': 'User'
    }

    # map_ maps param names to functions that retrieve the appropriate data
    # from the db.
    map_ = {
        'tags': h.getTags,
        'speakers': h.getSpeakers,
        'users': h.getUsers
    }

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in map_])
    result['utteranceTypes'] = h.utteranceTypes

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


def createNewFile(data):
    """Create a new File model object given a data dictionary provided by the
    user (as a JSON object).
    """

    file = File()

    # User-inputted string data
    file.name = h.normalize(data['name'])
    file.description = h.normalize(data['description'])
    file.utteranceType = h.normalize(data['utteranceType'])
    file.embeddedFileMarkup = h.normalize(data['embeddedFileMarkup'])
    file.embeddedFilePassword = h.normalize(data['embeddedFilePassword'])

    # User-inputted date: dateElicited
    file.dateElicited = data['dateElicited']
    file.MIMEtype = unicode(h.guess_type(file.name)[0])

    # Many-to-One
    if data['elicitor']:
        file.elicitor = data['elicitor']
    if data['speaker']:
        file.speaker = data['speaker']

    # Many-to-Many
    file.tags = [t for t in data['tags'] if t]
    file.forms = [f for f in data['forms'] if f]

    # OLD-generated Data
    now = datetime.datetime.utcnow()
    file.datetimeEntered = now
    file.datetimeModified = now
    file.enterer = Session.query(User).get(session['user'].id)

    # Write the file to disk (making sure it's unique and thereby potentially)
    # modifying file.name and calculate file.size.

    def getUniqueFilePath(filePath):
        """This function ensures a unique file path (without race conditions) by
        attempting to create the file using os.open.  If the file exists, an OS
        error is raised (or if the file is too long, an IO error is raised), and
        a new file is generated until a unique one is found.
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

    fileData = data['file']     # Base64 decoded in the FileCreateSchema
    filePath = os.path.join(config['app_conf']['permanent_store'], file.name)
    fileObject, filePath = getUniqueFilePath(filePath)
    file.name = os.path.split(filePath)[-1]
    fileObject.write(fileData)
    fileObject.close()
    file.size = os.path.getsize(filePath)

    # Restrict the entire file if it is associated to restricted forms.
    tags = [f.tags for f in file.forms]
    tags = [tag for tagList in tags for tag in tagList]
    restrictedTags = [tag for tag in tags if tag.name == u'restricted']
    if restrictedTags:
        restrictedTag = restrictedTags[0]
        if restrictedTag not in file.tags:
            file.tags.append(restrictedTag)

    return file

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updateFile function
# below.
CHANGED = None

def updateFile(file, data):
    """Update the input File model object given a data dictionary provided by
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
    setAttr(file, 'description', h.normalize(data['description']))
    setAttr(file, 'utteranceType', h.normalize(data['utteranceType']))
    setAttr(file, 'embeddedFileMarkup', h.normalize(data['embeddedFileMarkup']))
    setAttr(file, 'embeddedFilePassword', h.normalize(data['embeddedFilePassword']))

    # User-entered date: dateElicited
    if file.dateElicited != data['dateElicited']:
        file.dateElicited = data['dateElicited']
        CHANGED = True

    # Many-to-One Data
    if data['elicitor'] != file.elicitor:
        file.elicitor = data['elicitor']
        CHANGED = True
    if data['speaker'] != file.speaker:
        file.speaker = data['speaker']
        CHANGED = True

    # Many-to-Many Data: tags & forms
    # Update only if the user has made changes.
    formsToAdd = [f for f in data['forms'] if f]
    tagsToAdd = [t for t in data['tags'] if t]

    if set(formsToAdd) != set(file.forms):
        file.forms = formsToAdd
        CHANGED = True

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
        CHANGED = True

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        file.datetimeModified = datetime.datetime.utcnow()
        return file
    return CHANGED

def deleteFile(file):
    filePath = os.path.join(config['app_conf']['permanent_store'], file.name)
    os.remove(filePath)
    Session.delete(file)
    Session.commit()

