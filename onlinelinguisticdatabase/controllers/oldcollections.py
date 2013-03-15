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

"""Contains the :class:`OldcollectionsController` and its auxiliary functions.

.. module:: collections
   :synopsis: Contains the collections controller and its auxiliary functions.

"""

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
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import CollectionSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Collection, CollectionBackup, User, Form

log = logging.getLogger(__name__)

class OldcollectionsController(BaseController):
    """Generate responses to requests on collection resources.

    REST Controller styled on the Atom Publishing Protocol.

    The collections controller is one of the more complex ones.  A great deal of
    this complexity arised from the fact that collections can reference forms
    and other collections in the value of their ``contents`` attribute.  The
    propagation of restricted tags and associated forms and the generation of
    the html from these contents-with-references, necessitates some complex
    logic for updates and deletions.

    .. warning::

        There is a potential issue with collection-collection reference.  A
        restricted user can restrict their own collection *A* and that
        restriction would be propagated up the reference chain, possibly causing
        another collection *B* (that was not created by the updater) to become
        restricted. That is, collection-collection reference permits restricted
        users to indirectly restrict collections they would otherwise not be
        permitted to restrict. This will be bothersome to other restricted users
        since they will no longer be able to access the newly restricted
        collection *B*.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder('Collection', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of collection resources matching the input JSON query.

        :URL: ``SEARCH /collections`` (or ``POST /collections/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "orderBy": [ ... ]},
                 "paginator": { ... }}

            where the ``orderBy`` and ``paginator`` attributes are optional.

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
        """Return the data necessary to search the collection resources.

        :URL: ``GET /collections/new_search``
        :returns: ``{"searchParameters": {"attributes": { ... }, "relations": { ... }}``

        """

        return {'searchParameters': h.getSearchParameters(self.queryBuilder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /collections: Return all collections."""
        """Get all collection resources.

        :URL: ``GET /collections`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all collection resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
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
        """Create a new collection resource and return it.

        :URL: ``POST /collections``
        :request body: JSON object representing the collection to create.
        :returns: the newly created collection.

        """
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
        """Return the data necessary to create a new collection.

        :URL: ``GET /collections/new`` with optional query string parameters 
        :returns: a dictionary of lists of resources.

        .. note::
        
           See :func:`getNewEditCollectionData` to understand how the query
           string parameters can affect the contents of the lists in the
           returned dictionary.

        """
        return getNewEditCollectionData(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a collection and return it.
        
        :URL: ``PUT /collections/id``
        :Request body: JSON object representing the collection with updated attribute values.
        :param str id: the ``id`` value of the collection to be updated.
        :returns: the updated collection model.

        """
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
                        updateCollectionsThatReferenceThisCollection(collection, self.queryBuilder,
                                            restricted=restricted, contents_changed=contents_changed)
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
        """Delete an existing collection and return it.

        :URL: ``DELETE /collections/id``
        :param str id: the ``id`` value of the collection to be deleted.
        :returns: the deleted collection model.

        .. note::

           Only administrators and a collection's enterer can delete it.

        """
        collection = h.eagerloadCollection(Session.query(Collection)).get(id)
        if collection:
            if session['user'].role == u'administrator' or \
            collection.enterer is session['user']:
                collectionDict = collection.getDict()
                backupCollection(collectionDict)
                updateCollectionsThatReferenceThisCollection(collection, self.queryBuilder, deleted=True)
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
        """Return a collection.
        
        :URL: ``GET /collections/id``
        :param str id: the ``id`` value of the collection to be returned.
        :returns: a collection model object.

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
        """Return a collection and the data needed to update it.

        :URL: ``GET /collections/edit`` with optional query string parameters 
        :param str id: the ``id`` value of the collection that will be updated.
        :returns: a dictionary of the form::

                {"collection": {...}, "data": {...}}

            where the value of the ``collection`` key is a dictionary
            representation of the collection and the value of the ``data`` key
            is a dictionary containing the objects necessary to update a
            collection, viz. the return value of
            :func:`CollectionsController.new`

        .. note::
        
           This action can be thought of as a combination of
           :func:`CollectionsController.show` and
           :func:`CollectionsController.new`.  See
           :func:`getNewEditCollectionData` to understand how the query string
           parameters can affect the contents of the lists in the ``data``
           dictionary.

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
        """Return a collection and its previous versions.

        :URL: ``GET /collections/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            collection whose history is requested.
        :returns: a dictionary of the form::

                {"collection": { ... }, "previousVersions": [ ... ]}

            where the value of the ``collection`` key is the collection whose
            history is requested and the value of the ``previousVersions`` key
            is a list of dictionaries representing previous versions of the
            collection.

        """
        collection, previousVersions = h.getModelAndPreviousVersions('Collection', id)
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


################################################################################
# Backup collection
################################################################################

def backupCollection(collectionDict, datetimeModified=None):
    """Backup a collection.

    :param dict formDict: a representation of a collection model.
    :param ``datetime.datetime`` datetimeModified: the time of the collection's
        last update.
    :returns: ``None``

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

def getCollectionsReferenced(contents, user=None, unrestrictedUsers=None,
                             collectionId=None, patt=None):
    """Return the collections (recursively) referenced by the input ``contents`` value.
    
    That is, return all of the collections referenced in the input ``contents``
    value, plus all of the collections referenced in those collections, etc.

    :param unicode contents: the value of the ``contents`` attribute of a collection.
    :param user: the user model who made the request.
    :param list unrestrictedUsers: the unrestricted user models of the application.
    :param int collectionId: the ``id`` value of a collection.
    :param patt: a compiled regular expression object.
    :returns: a dictionary whose keys are collection ``id`` values and whose
        values are collection models.

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
    """Add a list of referenced form ids to values.
    
    :param dict values: data for creating or updating a collection
    :returns: ``values`` with a ``'forms'`` key whose value is a list of id integers.

    """
    contentsUnpacked = getUnicode('contentsUnpacked', values)
    values['forms'] = [int(id) for id in h.formReferencePattern.findall(contentsUnpacked)]
    return values

def addContentsUnpackedToValues(values, collectionsReferenced):
    """Add a ``'contentsUnpacked'`` value to values and return values.
    
    :param dict values: data for creating a collection.
    :param dict collectionsReferenced: keys are collection ``id`` values and 
        values are collection models.
    :returns: ``values`` updated.

    """
    contents = getUnicode('contents', values)
    values['contentsUnpacked'] = generateContentsUnpacked(contents, collectionsReferenced)
    return values

def getCollectionsReferencedInContents(collection, collectionsReferenced):
    """Get the immediately referenced collections of a collection.
    
    :param collection: a collection model.
    :param dict collectionsReferenced: keys are collection ``id`` values and 
        values are collection models.
    :returns: a list of collection models; useful in determining whether
        directly referenced collections are restricted.

    """
    return [collectionsReferenced[int(id)]
            for id in h.collectionReferencePattern.findall(collection.contents)]

def updateCollectionsThatReferenceThisCollection(collection, queryBuilder, **kwargs):
    """Update all collections that reference the input collection.
    
    :param collection: a collection model.
    :param queryBuilder: an :class:`SQLAQueryBuilder` instance.
    :param bool kwargs['contents_changed']: indicates whether the input
        collection's ``contents`` value has changed.
    :param bool kwargs['deleted']: indicates whether the input collection has
        just been deleted.
    :returns: ``None``

    Update the ``contents``, ``contentsUnpacked``, ``html`` and/or ``form``
    attributes of every collection that references the input collection plus all
    of the collections that reference those collections, etc.  This function is
    called upon successful update and delete requests.

    If the contents of the ``collection`` have changed (i.e.,
    ``kwargs['contents_changed']==True``) , then retrieve all collections
    that reference ``collection`` and all collections that reference those
    referers, etc., and update their ``contentsUnpacked``, ``html`` and
    ``forms`` attributes.

    If the ``collection`` has been deleted (i.e., ``kwargs['deleted']==True``),
    then recursively retrieve all collections referencing ``collection`` and
    update their ``contents``, ``contentsUnpacked``, ``html`` and ``forms``
    attributes.

    If ``collection`` has just been tagged as restricted (i.e.,
    ``kwargs['restricted']==True``), then recursively restrict all collections
    that reference it.

    In all cases, update the ``datetimeModified`` value of every collection that
    recursively references ``collection``.

    """
    def updateContentsUnpackedEtc(collection, **kwargs):
        deleted = kwargs.get('deleted', False)
        collectionId = kwargs.get('collectionId')
        if deleted:
            collection.contents = removeReferencesToThisCollection(collection.contents, collectionId)
        collectionsReferenced = getCollectionsReferenced(collection.contents)
        collection.contentsUnpacked = generateContentsUnpacked(
                                    collection.contents, collectionsReferenced)
        collection.html = h.getHTMLFromContents(collection.contentsUnpacked,
                                                  collection.markupLanguage)
        collection.forms = [Session.query(Form).get(int(id)) for id in
                    h.formReferencePattern.findall(collection.contentsUnpacked)]

    restricted = kwargs.get('restricted', False)
    contents_changed = kwargs.get('contents_changed', False)
    deleted = kwargs.get('deleted', False)
    if restricted or contents_changed or deleted:
        collectionsReferencingThisCollection = getCollectionsReferencingThisCollection(
            collection, queryBuilder)
        collectionsReferencingThisCollectionDicts = [c.getDict() for c in
                                        collectionsReferencingThisCollection]
        now = h.now()
        if restricted:
            restrictedTag = h.getRestrictedTag()
            [c.tags.append(restrictedTag) for c in collectionsReferencingThisCollection]
        if contents_changed:
            [updateContentsUnpackedEtc(c) for c in collectionsReferencingThisCollection]
        if deleted:
            [updateContentsUnpackedEtc(c, collectionId=collection.id, deleted=True)
             for c in collectionsReferencingThisCollection]
        [setattr(c, 'datetimeModified', now) for c in collectionsReferencingThisCollection]
        [backupCollection(cd, now) for cd in collectionsReferencingThisCollectionDicts]
        Session.add_all(collectionsReferencingThisCollection)
        Session.commit()

def getCollectionsReferencingThisCollection(collection, queryBuilder):
    """Return all collections that recursively reference ``collection``.
    
    That is, return all collections that reference ``collection`` plus all
    collections that reference those referencing collections, etc.
    
    :param collection: a collection model object.
    :param queryBuilder: an :class:`SQLAQueryBuilder` instance.
    :returns: a list of collection models.

    """
    patt = h.collectionReferencePattern.pattern.replace(
        '\d+', str(collection.id)).replace('\\', '')
    query = {'filter': ['Collection', 'contents', 'regex', patt]}
    result = queryBuilder.getSQLAQuery(query).all()
    for c in result[:]:
        result += getCollectionsReferencingThisCollection(c, queryBuilder)
    return result


def updateCollectionByDeletionOfReferencedForm(collection, referencedForm):
    """Update a collection based on the deletion of a form it references.

    This function is called in the :class:`FormsController` when a form is
    deleted.  It is called on each collection that references the deleted form
    and the changes to each of those collections are propagated through all of
    the collections that reference them, and so on.
    
    :param collection: a collection model object.
    :param referencedForm: a form model object.
    :returns: ``None``.

    """
    collectionDict = collection.getDict()
    collection.contents = removeReferencesToThisForm(collection.contents, referencedForm.id)
    collectionsReferenced = getCollectionsReferenced(collection.contents)
    collection.contentsUnpacked = generateContentsUnpacked(
                                collection.contents, collectionsReferenced)
    collection.html = h.getHTMLFromContents(collection.contentsUnpacked,
                                              collection.markupLanguage)
    collection.datetimeModified = datetime.datetime.utcnow()
    backupCollection(collectionDict, collection.datetimeModified)
    updateCollectionsThatReferenceThisCollection(
        collection, OldcollectionsController.queryBuilder, contents_changed=True)
    Session.add(collection)
    Session.commit()

def removeReferencesToThisForm(contents, formId):
    """Remove references to a form from the ``contents`` value of another collection.

    :param unicode contents: the value of the ``contents`` attribute of a collection.
    :param int formId: an ``id`` value of a form.
    :returns: the modified ``contents`` string.

    """
    patt = re.compile('[Ff]orm\[(%d)\]' % formId)
    return patt.sub('', contents)

def removeReferencesToThisCollection(contents, collectionId):
    """Remove references to a collection from the ``contents`` value of another collection.
    
    :param unicode contents: the value of the ``contents`` attribute of a collection.
    :param int collectionId: an ``id`` value of a collection.
    :returns: the modified ``contents`` string.

    """
    patt = re.compile('[cC]ollection[\[\(](%d)[\]\)]' % collectionId)
    return patt.sub('', contents)

def getUnicode(key, dict_):
    """Return ``dict_[key]``, making sure it defaults to a unicode object."""
    value = dict_.get(key, u'')
    if isinstance(value, unicode):
        return value
    elif isinstance(value, str):
        return unicode(value)
    return u''

def getContents(collectionId, collectionsReferenced):
    """Return the ``contents`` value of the collection with ``collectionId`` as its ``id`` value.

    :param int collectionId: the ``id`` value of a collection model.
    :param dict collectionsReferenced: the collections (recursively) referenced by a collection.
    :returns: the contents of a collection, or a warning message.

    """
    return getattr(collectionsReferenced[collectionId],
                   u'contents',
                   u'Collection %d has no contents.' % collectionId)

def generateContentsUnpacked(contents, collectionsReferenced, patt=None):
    """Generate the ``contentsUnpacked`` value of a collection.
    
    :param unicode contents: the value of the ``contents`` attribute of a collection
    :param dict collectionsReferenced: the collection models referenced by a
        collection; keys are collection ``id`` values.
    :param patt: a compiled regexp pattern object that matches collection references.
    :returns: a unicode object as a value for the ``contentsUnpacked`` attribute
        of a collection model.

    .. note::
    
        Circular, invalid and unauthorized reference chains are caught in the
        generation of ``collectionsReferenced``.

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
    """Return the collection such that ``collection.id==collectionId``.

    If the collection does not exist or if ``user`` is not authorized to access
    it, raise an appropriate error.

    :param int collectionId: the ``id`` value of a collection.
    :param user: a user model of the logged in user.
    :param list unrestrictedUsers: the unrestricted users of the system.
    :return: a collection model object.

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
    """Return the data necessary to create a new OLD collection or update an existing one.
    
    :param GET_params: the ``request.GET`` dictionary-like object generated by
        Pylons which contains the query string parameters of the request.
    :returns: A dictionary whose values are lists of objects needed to create or
        update collections.

    If ``GET_params`` has no keys, then return all data.  If ``GET_params`` does
    have keys, then for each key whose value is a non-empty string (and not a
    valid ISO 8601 datetime) add the appropriate list of objects to the return
    dictionary.  If the value of a key is a valid ISO 8601 datetime string, add
    the corresponding list of objects *only* if the datetime does *not* match
    the most recent ``datetimeModified`` value of the resource.  That is, a
    non-matching datetime indicates that the requester has out-of-date data.

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
    """Create a new collection.

    :param dict data: the collection to be created.
    :param dict collectionsReferenced: the collection models recursively referenced in ``data['contents']``.
    :returns: an SQLAlchemy model object representing the collection.

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
    """Update a collection model.

    :param collection: the collection model to be updated.
    :param dict data: representation of the updated collection.
    :param dict collectionsReferenced: the collection models recursively referenced in ``data['contents']``.
    :returns: a 3-tuple where the second and third elements are invariable
        booleans indicating whether the collection has become restricted or has
        had its ``contents`` value changed as a result of the update,
        respectively.  The first element is the updated collection or ``False``
        of the no update has occurred.

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
