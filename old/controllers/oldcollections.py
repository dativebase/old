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
from old.model import Collection, CollectionBackup, User, Form

log = logging.getLogger(__name__)

class OldcollectionsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol.

    The collections controller is one of the more complex.  A great deal of this
    complexity arised from the fact that collections can reference forms and
    other collections in the value of their contents attribute.  The propagation
    of restricted tags and associated forms and the generation of the html from
    these contents-with-references, necessitates some complex logic for updates.

    There is a potential issue with collection-collection reference.  A
    restricted user can restrict their own collection A and that restriction
    would be propagated up the reference chain, possibly causing another
    collection B (that was not created by the updater) to become restricted.
    That is, collection-collection reference permits restricted users to
    restrict collections they would otherwise not be permitted to restrict. This
    will be bothersome to other restricted users since they can no longer access
    the newly restricted collection B.  A user authorized to update collection
    B will be able to remove this restriction.
    """

    queryBuilder = SQLAQueryBuilder('Collection', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
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
        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            SQLAQuery = h.eagerloadCollection(
                self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query')))
            query = h.filterRestrictedModels('Collection', SQLAQuery)
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
        """GET /collections/new_search: Return the data necessary to inform a search
        on the collections resource.
        """
        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /collections: Return all collections."""
        try:
            query = h.eagerloadCollection(Session.query(Collection))
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            query = h.filterRestrictedModels('Collection', query)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """POST /collections: Create a new collection."""
        try:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            schema = CollectionSchema()
            values = json.loads(unicode(request.body, request.charset))
            collectionsReferenced = getCollectionsReferenced(values['contents'],
                                                        user, unrestrictedUsers)
            values = addContentsUnpackedToValues(values, collectionsReferenced)
            values = addFormIdsListToValues(values)
            state = h.getStateObject(values)
            data = schema.to_python(values, state)
            collection = createNewCollection(data, collectionsReferenced)
            Session.add(collection)
            Session.commit()
            return collection
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except InvalidCollectionReferenceError, e:
            response.status_int = 400
            return {'error': u'Invalid collection reference error: there is no collection with id %d' % e.args[0]}
        except UnauthorizedCollectionReferenceError:
            response.status_int = 403
            return {'error': u'Unauthorized collection reference error: you are not authorized to access collection %d' % e.args[0]}
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('GET')
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
        return getNewEditCollectionData(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /collections/id: Update an existing collection."""
        collection = h.eagerloadCollection(Session.query(Collection)).get(int(id))
        if collection:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, collection, unrestrictedUsers):
                try:
                    schema = CollectionSchema()
                    values = json.loads(unicode(request.body, request.charset))
                    collectionsReferenced = getCollectionsReferenced(
                                values['contents'], user, unrestrictedUsers, id)
                    values = addContentsUnpackedToValues(values, collectionsReferenced)
                    values = addFormIdsListToValues(values)
                    state = h.getStateObject(values)
                    data = schema.to_python(values, state)
                    collectionDict = collection.getDict()
                    collection, restricted, contents_changed = updateCollection(
                        collection, data, collectionsReferenced)
                    # collection will be False if there are no changes (cf. updateCollection).
                    if collection:
                        backupCollection(collectionDict, collection.datetimeModified)
                        updateCollectionsThatReferenceThisCollection(collection,
                                self.queryBuilder, restricted, contents_changed)
                        Session.add(collection)
                        Session.commit()
                        return collection
                    else:
                        response.status_int = 400
                        return {'error':
                            u'The update request failed because the submitted data were not new.'}
                except h.JSONDecodeError:
                    response.status_int = 400
                    return h.JSONDecodeErrorResponse
                except CircularCollectionReferenceError, e:
                    response.status_int = 400
                    return {'error':
                        u'Circular collection reference error: collection %d references collection %d.' % (id, e.args[0])}
                except InvalidCollectionReferenceError, e:
                    response.status_int = 400
                    return {'error': u'Invalid collection reference error: there is no collection with id %d' % e.args[0]}
                except UnauthorizedCollectionReferenceError:
                    response.status_int = 403
                    return {'error': u'Unauthorized collection reference error: you are not authorized to access collection %d' % e.args[0]}
                except Invalid, e:
                    response.status_int = 400
                    return {'errors': e.unpack_errors()}
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no collection with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /collections/id: Delete an existing collection.  Only the
        enterer and administrators can delete a collection.
        """
        collection = h.eagerloadCollection(Session.query(Collection)).get(id)
        if collection:
            if session['user'].role == u'administrator' or \
            collection.enterer is session['user']:
                collectionDict = collection.getDict()
                backupCollection(collectionDict)
                Session.delete(collection)
                Session.commit()
                return collection
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no collection with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /collections/id: Return a JSON object representation of the collection with
        id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """
        collection = h.eagerloadCollection(Session.query(Collection)).get(id)
        if collection:
            unrestrictedUsers = h.getUnrestrictedUsers()
            user = session['user']
            if h.userIsAuthorizedToAccessModel(user, collection, unrestrictedUsers):
                return collection
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no collection with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
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
        collection = h.eagerloadCollection(Session.query(Collection)).get(id)
        if collection:
            unrestrictedUsers = h.getUnrestrictedUsers()
            if h.userIsAuthorizedToAccessModel(
                                session['user'], collection, unrestrictedUsers):
                data = getNewEditCollectionData(request.GET)
                return {'data': data, 'collection': collection}
            else:
                response.status_int = 403
                return h.unauthorizedMsg
        else:
            response.status_int = 404
            return {'error': 'There is no collection with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
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
                return h.unauthorizedMsg
            else :
                return {'collection': collection,
                        'previousVersions': unrestrictedPreviousVersions}
        else:
            response.status_int = 404
            return {'error': 'No collections or collection backups match %s' % id}


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
        collection = h.eagerloadCollection(Session.query(Collection)).get(id)
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
# Reference-extraction functions
################################################################################

# The following set of functions generate data from the references in the contents
# attribute of a collection.  The two primary tasks are to generate values for
# the 'forms' and 'contentsUnpacked' attributes of the collection.  The three
# "public" functions are getCollectionsReferenced, addFormIdsListToValues and
# addContentsUnpackedToValues.  getCollectionsReferenced raises errors if
# collection references are invalid and returns a dict from reference ids to
# collection objects, which dict is used by addContentsUnpackedToValues, the
# output of the latter being used to generate the list of referenced forms.

def getCollectionsReferenced(contents, user=None, unrestrictedUsers=None, collectionId=None, patt=None):
    """Return a dict of the form {id: collection} where the keys are the ids of
    all the collections referenced in the contents and all of the collection ids
    referenced in those collections, etc., and the values are the collection
    objects themselves.  This function is called recursively.
    """
    patt = patt or re.compile(h.collectionReferencePattern)
    collectionsReferenced = dict([(int(id), getCollection(int(id), user, unrestrictedUsers))
                                  for id in patt.findall(contents)])
    temp = collectionsReferenced.copy()
    if collectionId in collectionsReferenced:
        raise CircularCollectionReferenceError(collectionId)
    [collectionsReferenced.update(getCollectionsReferenced(
        collectionsReferenced[id].contents, user, unrestrictedUsers, collectionId, patt))
     for id in temp]
    return collectionsReferenced

def addFormIdsListToValues(values):
    """Add a list of form ids (extracted from contentsUnpacked) to the values
    dict and return values.
    """
    contentsUnpacked = getUnicode('contentsUnpacked', values)
    values['forms'] = [int(id) for id in h.formReferencePattern.findall(contentsUnpacked)]
    return values

def addContentsUnpackedToValues(values, collectionsReferenced):
    """Add a 'contentsUnpacked' value to values and return values.
    """
    contents = getUnicode('contents', values)
    values['contentsUnpacked'] = generateContentsUnpacked(contents, collectionsReferenced)
    return values

def getCollectionsReferencedInContents(collection, collectionsReferenced):
    """Return the list of collections referenced in the contents field of the
    input collection.  collectionsReferenced is a pre-generated dict from ids to
    collections that obviates the need to query the database.  The output of this
    function is useful in determining whether directly referenced collections are
    restricted and deciding, on that basis, whether to restrict the present collection.
    """
    return [collectionsReferenced[int(id)]
            for id in h.collectionReferencePattern.findall(collection.contents)]

def updateCollectionsThatReferenceThisCollection(collection, queryBuilder, restricted, contents_changed):
    """If the contents of this collection have changed (i.e., contents_changed=True)
    or this collection has just been tagged as restricted (i.e., restricted=True),
    then retrieve all collections that reference this collection and all collections
    that reference those referers, etc., and (1) tag them as restricted (if
    appropriate), (2) update their contentsUnpacked and html attributes (if
    appropriate) and (3) update their datetimeModified attribute.
    """
    def updateContentsUnpackedEtc(collection):
        collectionsReferenced = getCollectionsReferenced(collection.contents)
        collection.contentsUnpacked = generateContentsUnpacked(
                                    collection.contents, collectionsReferenced)
        collection.html = h.getHTMLFromContents(collection.contentsUnpacked,
                                                  collection.markupLanguage)
        collection.forms = [Session.query(Form).get(int(id)) for id in
                    h.formReferencePattern.findall(collection.contentsUnpacked)]

    if restricted or contents_changed:
        collectionsReferencingThisCollection = getCollectionsReferencingThisCollection(
            collection, queryBuilder)
        now = h.now()
        if restricted:
            restrictedTag = h.getRestrictedTag()
            [c.tags.append(restrictedTag) for c in collectionsReferencingThisCollection]
        if contents_changed:
            [updateContentsUnpackedEtc(c) for c in collectionsReferencingThisCollection]
        [setattr(c, 'datetimeModified', now) for c in collectionsReferencingThisCollection]
        Session.add_all(collectionsReferencingThisCollection)
        Session.commit()

def getCollectionsReferencingThisCollection(collection, queryBuilder):
    patt = h.collectionReferencePattern.pattern.replace(
        '\d+', str(collection.id)).replace('\\', '')
    query = {'filter': ['Collection', 'contents', 'regex', patt]}
    result = queryBuilder.getSQLAQuery(query).all()
    for c in result[:]:
        result += getCollectionsReferencingThisCollection(c, queryBuilder)
    return result


# PRIVATE FUNCTIONS

def getUnicode(key, dict_):
    """Return dict_[key], making sure it defaults to a unicode string.
    """
    value = dict_.get(key, u'')
    if isinstance(value, unicode):
        return value
    elif isinstance(value, str):
        return unicode(value)
    return u''

def getContents(collectionId, collectionsReferenced):
    """Attempt to return the contents of the collection with id=collectionId.
    If the collection id is invalid or the collection has no stringy contents,
    return an appropriate warning message.
    """
    return getattr(collectionsReferenced[collectionId],
                   u'contents',
                   u'Collection %d has no contents.' % collectionId)

def generateContentsUnpacked(contents, collectionsReferenced, patt=None):
    """Generate the value for the contentsUnpacked attribute for a collection
    based on the value of its contents attribute.  This function calls itself
    recursively.  The collectionsReferenced dict is generated earlier and
    obviates repeated database queries.  Note also that circular, invalid and
    unauthorized reference chains are caught in the generation of collectionsReferenced.
    """
    patt = patt or re.compile(h.collectionReferencePattern)
    return patt.sub(
        lambda m: generateContentsUnpacked(
            getContents(int(m.group(1)), collectionsReferenced),
            collectionsReferenced, patt),
        contents
    )

# Three custom error classes to raise when collection.contents are invalid
class CircularCollectionReferenceError(Exception):
    pass

class InvalidCollectionReferenceError(Exception):
    pass

class UnauthorizedCollectionReferenceError(Exception):
    pass

def getCollection(collectionId, user, unrestrictedUsers):
    """Return the collection with collectionId or, if the collection does not
    exist or is restricted, raise an appropriate error.
    """
    collection = Session.query(Collection).get(collectionId)
    if collection:
        if user is None or unrestrictedUsers is None or \
        h.userIsAuthorizedToAccessModel(user, collection, unrestrictedUsers):
            return collection
        else:
            raise UnauthorizedCollectionReferenceError(collectionId)
    raise InvalidCollectionReferenceError(collectionId)


################################################################################
# Get data for requests to /collections/new and /collections/{id}/edit requests
################################################################################

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
        'speakers': h.getMiniDictsGetter('Speaker'),
        'users': h.getMiniDictsGetter('User'),
        'tags': h.getMiniDictsGetter('Tag'),
        'sources': h.getMiniDictsGetter('Source')
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

################################################################################
# Collection Create & Update Functions
################################################################################

def createNewCollection(data, collectionsReferenced):
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
    collection.contentsUnpacked = h.normalize(data['contentsUnpacked'])
    collection.html = h.getHTMLFromContents(collection.contentsUnpacked,
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

    # Restrict the entire collection if it is associated to restricted forms or
    # files or if it references a restricted collection in its contents field.
    immediatelyReferencedCollections = getCollectionsReferencedInContents(
                                            collection, collectionsReferenced)
    tags = [f.tags for f in collection.files + collection.forms + immediatelyReferencedCollections]
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


def updateCollection(collection, data, collectionsReferenced):
    """Update the input Collection model object given a data dictionary provided by
    the user (as a JSON object).  If changed is not set to true in the course
    of attribute setting, then None is returned and no update occurs.
    """
    changed = False
    restricted = False
    contents_changed = False

    # Unicode Data
    changed = h.setAttr(collection, 'title', h.normalize(data['title']), changed)
    changed = h.setAttr(collection, 'type', h.normalize(data['type']), changed)
    changed = h.setAttr(collection, 'url', h.normalize(data['url']), changed)
    changed = h.setAttr(collection, 'description', h.normalize(data['description']), changed)
    changed = h.setAttr(collection, 'markupLanguage', h.normalize(data['markupLanguage']), changed)
    submittedContents = h.normalize(data['contents'])
    if collection.contents != submittedContents:
        collection.contents = submittedContents
        contents_changed = changed = True
    changed = h.setAttr(collection, 'contentsUnpacked', h.normalize(data['contentsUnpacked']), changed)
    changed = h.setAttr(collection, 'html', h.getHTMLFromContents(collection.contentsUnpacked,
                                                      collection.markupLanguage), changed)

    # User-entered date: dateElicited
    changed = h.setAttr(collection, 'dateElicited', data['dateElicited'], changed)

    # Many-to-One Data
    changed = h.setAttr(collection, 'elicitor', data['elicitor'], changed)
    changed = h.setAttr(collection, 'speaker', data['speaker'], changed)
    changed = h.setAttr(collection, 'source', data['source'], changed)

    # Many-to-Many Data: files, forms & tags
    # Update only if the user has made changes.
    filesToAdd = [f for f in data['files'] if f]
    formsToAdd = [f for f in data['forms'] if f]
    tagsToAdd = [t for t in data['tags'] if t]

    if set(filesToAdd) != set(collection.files):
        collection.files = filesToAdd
        changed = True

    if set(formsToAdd) != set(collection.forms):
        collection.forms = formsToAdd
        changed = True

    # Restrict the entire collection if it is associated to restricted forms or
    # files or if it references a restricted collection.
    tags = [f.tags for f in collection.files + collection.forms + collectionsReferenced.values()]
    tags = [tag for tagList in tags for tag in tagList]
    restrictedTags = [tag for tag in tags if tag.name == u'restricted']
    if restrictedTags:
        restrictedTag = restrictedTags[0]
        if restrictedTag not in tagsToAdd:
            tagsToAdd.append(restrictedTag)

    if set(tagsToAdd) != set(collection.tags):
        if u'restricted' in [t.name for t in tagsToAdd] and \
        u'restricted' not in [t.name for t in collection.tags]:
            restricted = True
        collection.tags = tagsToAdd
        changed = True

    if changed:
        collection.datetimeModified = datetime.datetime.utcnow()
        return collection, restricted, contents_changed
    return changed, restricted, contents_changed
