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
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('User', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /users: Return all users."""
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
        """POST /users: Create a new user."""
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
        """GET /users/new: Return the data necessary to create a new OLD user.

        Return a JSON object with the following properties: roles, orthographies,
        markupLanguages, the value of each of which is an array that
        is either empty or contains the appropriate objects.

        See the getNewUserData function to understand how the GET
        params can affect the contents of the arrays.
        """
        return getNewUserData(request.GET)

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor', 'viewer'], None, True)
    def update(self, id):
        """PUT /users/id: Update an existing user."""
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
        """DELETE /users/id: Delete an existing user."""
        user = Session.query(User).get(id)
        if user:
            h.destroyResearcherDirectory(user)
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
        """GET /users/id: Return a JSON object representation of the user with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
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
        """GET /users/id/edit: Return the data necessary to update an existing
        OLD user; here we return only the user and
        an empty JSON object.
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
    """Return the data necessary to create a new user or update
    an existing one.  The GET_params parameter is the request.GET dictionary-
    like object generated by Pylons.

    If no parameters are provided (i.e., GET_params is empty), then retrieve all
    data (i.e., roles, orthographies and markupLanguages) and return them.

    If parameters are specified, then for each parameter whose value is a
    non-empty string (and is not a valid ISO 8601 datetime), retrieve and
    return the appropriate list of objects.

    If the value of a parameter is a valid ISO 8601 datetime string,
    retrieve and return the appropriate list of objects *only* if the
    datetime param does *not* match the most recent datetimeModified value
    of the relevant data store.  This makes sense because a non-match indicates
    that the requester has out-of-date data.
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
    """Create a new user model object given a data dictionary
    provided by the user (as a JSON object).
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

    # Create the user's directory in /files/researchers/
    h.createResearcherDirectory(user)

    return user


def updateUser(user, data):
    """Update the input user model object given a data dictionary
    provided by the user (as a JSON object).  If changed is not set to true in
    the course of attribute setting, then None is returned and no update occurs.
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
            h.renameResearcherDirectory(user.username, username)
        changed = h.setAttr(user, 'username', username, changed)

    # Many-to-One Data
    changed = h.setAttr(user, 'inputOrthography', data['inputOrthography'], changed)
    changed = h.setAttr(user, 'outputOrthography', data['outputOrthography'], changed)

    if changed:
        user.datetimeModified = datetime.datetime.utcnow()
        return user
    return changed
