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

"""Contains the :class:`UsersController` and its auxiliary functions.

.. module:: users
   :synopsis: Contains the users controller and its auxiliary functions.

"""

import logging
import datetime
import re
import simplejson as json

from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import UserSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import User

log = logging.getLogger(__name__)

class UsersController(BaseController):
    """Generate responses to requests on user resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder('User', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all user resources.

        :URL: ``GET /users`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all user resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(User)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator'])
    def create(self):
        """Create a new user resource and return it.

        :URL: ``POST /users``
        :request body: JSON object representing the user to create.
        :returns: the newly created user.

        .. note::
        
            Only administrators are authorized to create users.

        """
        try:
            schema = UserSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            user = createNewUser(data)
            Session.add(user)
            Session.commit()
            return user.getFullDict()
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
        """Return the data necessary to create a new user.

        :URL: ``GET /users/new`` with optional query string parameters .
        :returns: a dictionary of lists of resources.

        .. note::
        
           See :func:`getNewUserData` to understand how the query string
           parameters can affect the contents of the lists in the returned
           dictionary.

        """

        return getNewUserData(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor', 'viewer'], None, True)
    def update(self, id):
        """Update a user and return it.
        
        :URL: ``PUT /users/id``
        :Request body: JSON object representing the user with updated attribute values.
        :param str id: the ``id`` value of the user to be updated.
        :returns: the updated user model.

        """
        user = Session.query(User).get(int(id))
        if user:
            try:
                schema = UserSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.userToUpdate = user.getFullDict()
                state.user = session['user'].getFullDict()
                data = schema.to_python(values, state)
                user = updateUser(user, data)
                # user will be False if there are no changes (cf. updateUser).
                if user:
                    Session.add(user)
                    Session.commit()
                    return user.getFullDict()
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
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator'])
    def delete(self, id):
        """Delete an existing user and return it.

        :URL: ``DELETE /users/id``
        :param str id: the ``id`` value of the user to be deleted.
        :returns: the deleted user model.

        """
        user = Session.query(User).get(id)
        if user:
            h.destroyUserDirectory(user)
            Session.delete(user)
            Session.commit()
            return user.getFullDict()
        else:
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a user.
        
        :URL: ``GET /users/id``
        :param str id: the ``id`` value of the user to be returned.
        :returns: a user model object.

        """
        user = Session.query(User).get(id)
        if user:
            return user
        else:
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor', 'viewer'], userIDIsArgs1=True)
    def edit(self, id):
        """Return a user resource and the data needed to update it.

        :URL: ``GET /users/edit``
        :param str id: the ``id`` value of the user that will be updated.
        :returns: a dictionary of the form::

                {"user": {...}, "data": {...}}

            where the value of the ``user`` key is a dictionary representation
            of the user and the value of the ``user`` key is a dictionary of
            lists of resources.

        .. note::

           See :func:`getNewUserData` to understand how the query string
           parameters can affect the contents of the lists in the returned
           dictionary.

        """
        user = Session.query(User).get(id)
        if user:
            data = getNewUserData(request.GET)
            return {'data': data, 'user': user.getFullDict()}
        else:
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}


################################################################################
# User Create & Update Functions
################################################################################

def getNewUserData(GET_params):
    """Return the data necessary to create a new OLD user or update an existing one.
    
    :param GET_params: the ``request.GET`` dictionary-like object generated by
        Pylons which contains the query string parameters of the request.
    :returns: A dictionary whose values are lists of objects needed to create or
        update user.

    If ``GET_params`` has no keys, then return all data.  If ``GET_params`` does
    have keys, then for each key whose value is a non-empty string (and not a
    valid ISO 8601 datetime) add the appropriate list of objects to the return
    dictionary.  If the value of a key is a valid ISO 8601 datetime string, add
    the corresponding list of objects *only* if the datetime does *not* match
    the most recent ``datetimeModified`` value of the resource.  That is, a
    non-matching datetime indicates that the requester has out-of-date data.

    """
    # modelNameMap maps param names to the OLD model objects from which they are
    # derived.
    modelNameMap = {'orthographies': 'Orthography'}

    # getterMap maps param names to getter functions that retrieve the
    # appropriate data from the db.
    getterMap = {'orthographies': h.getMiniDictsGetter('Orthography')}

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in getterMap])
    result['roles'] = h.userRoles
    result['markupLanguages'] = h.markupLanguages

    # There are GET params, so we are selective in what we return.
    if GET_params:
        for key in getterMap:
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
                    modelNameMap[key]):
                        result[key] = getterMap[key]()
                else:
                    result[key] = getterMap[key]()

    # There are no GET params, so we get everything from the db and return it.
    else:
        for key in getterMap:
            result[key] = getterMap[key]()

    return result

def createNewUser(data):
    """Create a new user.

    :param dict data: the data for the user to be created.
    :returns: an SQLAlchemy model object representing the user.

    """
    user = User()
    user.salt = h.generateSalt()
    user.password = unicode(h.encryptPassword(data['password'], str(user.salt)))
    user.username = h.normalize(data['username'])
    user.firstName = h.normalize(data['firstName'])
    user.lastName = h.normalize(data['lastName'])
    user.email = h.normalize(data['email'])
    user.affiliation = h.normalize(data['affiliation'])
    user.role = h.normalize(data['role'])
    user.markupLanguage = h.normalize(data['markupLanguage'])
    user.pageContent = h.normalize(data['pageContent'])
    user.html = h.getHTMLFromContents(user.pageContent, user.markupLanguage)

    # Many-to-One Data: input and output orthographies
    if data['inputOrthography']:
        user.inputOrthography= data['inputOrthography']
    if data['outputOrthography']:
        user.outputOrthography = data['outputOrthography']

    # OLD-generated Data
    user.datetimeModified = datetime.datetime.utcnow()

    # Create the user's directory
    h.createUserDirectory(user)

    return user


def updateUser(user, data):
    """Update a user.

    :param user: the user model to be updated.
    :param dict data: representation of the updated user.
    :returns: the updated user model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False

    # Unicode Data
    changed = h.setAttr(user, 'firstName', h.normalize(data['firstName']), changed)
    changed = h.setAttr(user, 'lastName', h.normalize(data['lastName']), changed)
    changed = h.setAttr(user, 'email', h.normalize(data['email']), changed)
    changed = h.setAttr(user, 'affiliation', h.normalize(data['affiliation']), changed)
    changed = h.setAttr(user, 'role', h.normalize(data['role']), changed)
    changed = h.setAttr(user, 'pageContent', h.normalize(data['pageContent']), changed)
    changed = h.setAttr(user, 'markupLanguage', h.normalize(data['markupLanguage']), changed)
    changed = h.setAttr(user, 'html', h.getHTMLFromContents(user.pageContent, user.markupLanguage), changed)

    # username and password need special treatment: a value of None means that
    # these should not be updated.
    if data['password'] is not None:
        changed = h.setAttr(user, 'password',
                    unicode(h.encryptPassword(data['password'], str(user.salt))), changed)
    if data['username'] is not None:
        username = h.normalize(data['username'])
        if username != user.username:
            h.renameUserDirectory(user.username, username)
        changed = h.setAttr(user, 'username', username, changed)

    # Many-to-One Data
    changed = h.setAttr(user, 'inputOrthography', data['inputOrthography'], changed)
    changed = h.setAttr(user, 'outputOrthography', data['outputOrthography'], changed)

    if changed:
        user.datetimeModified = datetime.datetime.utcnow()
        return user
    return changed
