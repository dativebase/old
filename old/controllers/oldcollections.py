import logging
import datetime
import re
import os
from uuid import uuid4
import simplejson as json
from string import letters, digits
from random import sample
from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from pylons.controllers.util import forward
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from old.lib.base import BaseController
from old.lib.schemata import CollectionSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Collection, CollectionBackup, User

log = logging.getLogger(__name__)

class OldcollectionsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Collection')

    @restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """SEARCH /collections: Return all collections matching the filter passed as JSON in
        the request body.  Note: POST /collections/search also routes to this action.
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
            query = h.filterRestrictedModels('Collection', SQLAQuery)
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
        """GET /collections: Return all collections."""
        # url('collections')
        response.content_type = 'application/json'
        try:
            query = Session.query(Collection)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels('Collection', query)
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
        """POST /collections: Create a new collection."""
        # url('collections')
        response.content_type = 'application/json'
        try:
            schema = CollectionSchema()
            values = json.loads(unicode(request.body, request.charset))
            values = addFormIdsListToValues(values)
            state = h.getStateObject(values)
            result = schema.to_python(values, state)
        except h.JSONDecodeError:
            response.status_int = 400
            result = h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            result = json.dumps({'errors': e.unpack_errors()})
        else:
            collection = createNewCollection(result)
            Session.add(collection)
            Session.commit()
            result = json.dumps(collection, cls=h.JSONOLDEncoder)
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """GET /new_collection: Return the data necessary to create a new OLD collection.

        Return a JSON object with the following properties: 'collectionTypes',
        'markupLanguages', 'tags', 'speakers', 'users' and 'sources', the value
        of each of which is an array that is either empty or contains the
        appropriate objects.

        See the getNewEditCollectionData function to understand how the GET params can
        affect the contents of the arrays.
        """

        response.content_type = 'application/json'
        result = getNewEditCollectionData(request.GET)
        return json.dumps(result, cls=h.JSONOLDEncoder)

    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /collections/id: Update an existing collection."""

        response.content_type = 'application/json'
        collection = Session.query(Collection).get(int(id))
        if collection:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, collection, unrestrictedUsers):
                try:
                    schema = CollectionSchema()
                    values = json.loads(unicode(request.body, request.charset))
                    values = addFormIdsListToValues(values)
                    state = h.getStateObject(values)
                    result = schema.to_python(values, state)
                except h.JSONDecodeError:
                    response.status_int = 400
                    result = h.JSONDecodeErrorResponse
                except Invalid, e:
                    response.status_int = 400
                    result = json.dumps({'errors': e.unpack_errors()})
                else:
                    collectionDict = collection.getDict()
                    collection = updateCollection(collection, result)
                    # collection will be False if there are no changes (cf. updateCollection).
                    if collection:
                        backupCollection(collectionDict, collection.datetimeModified)
                        Session.add(collection)
                        Session.commit()
                        result = json.dumps(collection, cls=h.JSONOLDEncoder)
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
            result = json.dumps({'error': 'There is no collection with id %s' % id})
        return result

    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /collections/id: Delete an existing collection.  Only the
        enterer and administrators can delete a collection.
        """

        response.content_type = 'application/json'
        collection = Session.query(Collection).get(id)
        if collection:
            if session['user'].role == u'administrator' or \
            collection.enterer is session['user']:
                collectionDict = collection.getDict()
                backupCollection(collectionDict)
                Session.delete(collection)
                Session.commit()
                result = json.dumps(collection, cls=h.JSONOLDEncoder)
            else:
                response.status_int = 403
                result = h.unauthorizedJSONMsg
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no collection with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /collections/id: Return a JSON object representation of the collection with
        id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """

        response.content_type = 'application/json'
        collection = Session.query(Collection).get(id)
        if collection:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, collection, unrestrictedUsers):
                result = json.dumps(collection, cls=h.JSONOLDEncoder)
            else:
                response.status_int = 403
                result = h.unauthorizedJSONMsg
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no collection with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /collections/id/edit: Return the data necessary to update an
        existing OLD collection, i.e., the collection's properties and the
        necessary additional data, i.e., users, speakers, etc.

        This action can be thought of as a combination of the 'show' and 'new'
        actions.  The output will be a JSON object of the form

            {collection: {...}, data: {...}},

        where output.collection is an object containing the collection's
        properties (cf. the output of show) and output.data is an object
        containing the data required to add a new collection (cf. the output of
        new).

        GET parameters will affect the value of output.data in the same way as
        for the new action, i.e., no params will result in all the necessary
        output.data being retrieved from the db while specified params will
        result in selective retrieval (see getNewEditCollectionData for details).
        """

        response.content_type = 'application/json'
        collection = Session.query(Collection).get(id)
        if collection:
            unrestrictedUsers = h.getUnrestrictedUsers()
            if h.userIsAuthorizedToAccessModel(
                                session['user'], collection, unrestrictedUsers):
                data = getNewEditCollectionData(request.GET)
                result = {'data': data, 'collection': collection}
                result = json.dumps(result, cls=h.JSONOLDEncoder)
            else:
                response.status_int = 403
                result = h.unauthorizedJSONMsg
        else:
            response.status_int = 404
            result = json.dumps({'error': 'There is no collection with id %s' % id})
        return result

    @restrict('GET')
    @h.authenticate
    def history(self, id):
        """GET /collections/history/id: Return a JSON object representation of the collection and its previous versions.

        The id parameter can be either an integer id or a UUID.  If no collection and
        no collection backups match id, then a 404 is returned.  Otherwise a 200 is
        returned (or a 403 if the restricted keyword is relevant).  See below:

        collection          None    None          collection collection
        previousVersions    []      [1, 2,...]    []         [1, 2,...]
        response            404     200/403       200/403    200/403
        """

        response.content_type = 'application/json'
        collection, previousVersions = getCollectionAndPreviousVersions(id)
        if collection or previousVersions:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            accessible = h.userIsAuthorizedToAccessModel
            unrestrictedPreviousVersions = [cb for cb in previousVersions
                                    if accessible(user, cb, unrestrictedUsers)]
            collectionIsRestricted = collection and not accessible(user, collection, unrestrictedUsers)
            previousVersionsAreRestricted = previousVersions and not unrestrictedPreviousVersions
            if collectionIsRestricted or previousVersionsAreRestricted :
                response.status_int = 403
                result = h.unauthorizedJSONMsg
            else :
                result = {'collection': collection,
                          'previousVersions': unrestrictedPreviousVersions}
                result = json.dumps(result, cls=h.JSONOLDEncoder)
        else:
            response.status_int = 404
            result = json.dumps({'error': 'No collections or collection backups match %s' % id})
        return result


def getCollectionAndPreviousVersions(id):
    """The id parameter is a string representing either an integer id or a UUID.
    Return the collection such that collection.id==id or collection.UUID==UUID
    (if there is one) as well as all collection backups such that
    collectionBackup.UUID==id or collectionBackup.collection_id==id.
    """

    collection = None
    previousVersions = []
    try:
        id = int(id)
        collection = Session.query(Collection).get(id)
        if collection:
            previousVersions = h.getCollectionBackupsByUUID(collection.UUID)
        else:
            previousVersions = h.getCollectionBackupsByCollectionId(id)
    except ValueError:
        try:
            UUID = unicode(h.UUID(id))
            form = h.getCollectionByUUID(UUID)
            previousVersions = h.getCollectionBackupsByUUID(UUID)
        except (AttributeError, ValueError):
            pass    # id is neither an integer nor a UUID
    return (collection, previousVersions)


################################################################################
# Backup collection
################################################################################

def backupCollection(collectionDict, datetimeModified=None):
    """When a collection is updated or deleted, it is first added to the
    collectionbackup table.
    """

    collectionBackup = CollectionBackup()
    collectionBackup.vivify(collectionDict, session['user'], datetimeModified)
    Session.add(collectionBackup)


################################################################################
# Collection Create & Update Functions
################################################################################

def addFormIdsListToValues(values):
    contents = getContentsFromCollectionInputValues(values)
    values['forms'] = [int(id) for id in h.formReferencePattern.findall(contents)]
    return values

def getContentsFromCollectionInputValues(values):
    contents = values.get('contents', u'')
    if not isinstance(contents, (unicode, str)):
        return u''
    else:
        return unicode(contents)


def getNewEditCollectionData(GET_params):
    """Return the data necessary to create a new OLD collection or update an existing
    one.  The GET_params parameter is the request.GET dictionary-like object
    generated by Pylons.

    If no parameters are provided (i.e., GET_params is empty), then retrieve all
    data (i.e., users, speakers, etc.) from the db and return it.

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
        'speakers': 'Speaker',
        'users': 'User',
        'tags': 'Tag',
        'sources': 'Source'
    }

    # map_ maps param names to functions that retrieve the appropriate data
    # from the db.
    map_ = {
        'speakers': h.getSpeakers,
        'users': h.getUsers,
        'tags': h.getTags,
        'sources': h.getSources
    }

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in map_])
    result['collectionTypes'] = h.collectionTypes
    result['markupLanguages'] = h.markupLanguages

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


def createNewCollection(data):
    """Create a new Collection model object given a data dictionary provided by the
    user (as a JSON object).
    """

    collection = Collection()
    collection.UUID = unicode(uuid4())

    # User-inputted string data
    collection.title = h.normalize(data['title'])
    collection.type = h.normalize(data['type'])
    collection.url = h.normalize(data['url'])
    collection.description = h.normalize(data['description'])
    collection.markupLanguage = h.normalize(data['markupLanguage'])
    collection.contents = h.normalize(data['contents'])
    collection.html = h.getHTMLFromCollectionContents(collection.contents,
                                                      collection.markupLanguage)

    # User-inputted date: dateElicited
    collection.dateElicited = data['dateElicited']

    # Many-to-One
    if data['elicitor']:
        collection.elicitor = data['elicitor']
    if data['speaker']:
        collection.speaker = data['speaker']
    if data['source']:
        collection.source = data['source']

    # Many-to-Many: tags, files & forms
    collection.tags = [t for t in data['tags'] if t]
    collection.files = [f for f in data['files'] if f]
    collection.forms = [f for f in data['forms'] if f]

    # Restrict the entire collection if it is associated to restricted forms or files.
    tags = [f.tags for f in collection.files + collection.forms]
    tags = [tag for tagList in tags for tag in tagList]
    restrictedTags = [tag for tag in tags if tag.name == u'restricted']
    if restrictedTags:
        restrictedTag = restrictedTags[0]
        if restrictedTag not in collection.tags:
            collection.tags.append(restrictedTag)

    # OLD-generated Data
    now = datetime.datetime.utcnow()
    collection.datetimeEntered = now
    collection.datetimeModified = now
    collection.enterer = Session.query(User).get(session['user'].id)


    return collection

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updateCollection function
# below.
CHANGED = None

def updateCollection(collection, data):
    """Update the input Collection model object given a data dictionary provided by
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
    setAttr(collection, 'title', h.normalize(data['title']))
    setAttr(collection, 'type', h.normalize(data['type']))
    setAttr(collection, 'url', h.normalize(data['url']))
    setAttr(collection, 'description', h.normalize(data['description']))
    setAttr(collection, 'markupLanguage', h.normalize(data['markupLanguage']))
    setAttr(collection, 'contents', h.normalize(data['contents']))
    setAttr(collection, 'html', h.getHTMLFromCollectionContents(
        collection.contents, collection.markupLanguage))

    # User-entered date: dateElicited
    if collection.dateElicited != data['dateElicited']:
        collection.dateElicited = data['dateElicited']
        CHANGED = True

    # Many-to-One Data
    if data['elicitor'] != collection.elicitor:
        collection.elicitor = data['elicitor']
        CHANGED = True
    if data['speaker'] != collection.speaker:
        collection.speaker = data['speaker']
        CHANGED = True
    if data['source'] != collection.source:
        collection.source = data['source']
        CHANGED = True

    # Many-to-Many Data: files, forms & tags
    # Update only if the user has made changes.
    filesToAdd = [f for f in data['files'] if f]
    formsToAdd = [f for f in data['forms'] if f]
    tagsToAdd = [t for t in data['tags'] if t]

    if set(filesToAdd) != set(collection.files):
        collection.files = filesToAdd
        CHANGED = True

    if set(formsToAdd) != set(collection.forms):
        collection.forms = formsToAdd
        CHANGED = True

    # Restrict the entire collection if it is associated to restricted forms or files.
    tags = [f.tags for f in collection.files + collection.forms]
    tags = [tag for tagList in tags for tag in tagList]
    restrictedTags = [tag for tag in tags if tag.name == u'restricted']
    if restrictedTags:
        restrictedTag = restrictedTags[0]
        if restrictedTag not in tagsToAdd:
            tagsToAdd.append(restrictedTag)

    if set(tagsToAdd) != set(collection.tags):
        collection.tags = tagsToAdd
        CHANGED = True

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        collection.datetimeModified = datetime.datetime.utcnow()
        return collection
    return CHANGED
