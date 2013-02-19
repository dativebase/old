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

from old.lib.base import BaseController
from old.lib.schemata import OrthographySchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Orthography

log = logging.getLogger(__name__)

class OrthographiesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Orthography', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /orthographies: Return all orthographies."""
        try:
            query = Session.query(Orthography)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """POST /orthographies: Create a new orthography."""
        try:
            schema = OrthographySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            orthography = createNewOrthography(data)
            Session.add(orthography)
            Session.commit()
            return orthography
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
        """GET /orthographies/new: Return the data necessary to create a new OLD
        orthography.  NOTHING TO RETURN HERE ...
        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /orthographies/id: Update an existing orthography.  Note that
        contributors can only update orthographies that are not used in the
        active application settings.
        """
        orthography = Session.query(Orthography).get(int(id))
        user = session['user']
        if orthography:
            appSet = h.getApplicationSettings()
            if user.role == u'administrator' or orthography not in (
            appSet.storageOrthography, appSet.inputOrthography, appSet.outputOrthography):
                try:
                    schema = OrthographySchema()
                    values = json.loads(unicode(request.body, request.charset))
                    result = schema.to_python(values)
                    orthography = updateOrthography(orthography, result)
                    # orthography will be False if there are no changes (cf. updateOrthography).
                    if orthography:
                        Session.add(orthography)
                        Session.commit()
                        return orthography
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
                response.status = 403
                return {'error': u'Only administrators are permitted to update orthographies that are used in the active application settings.'}
        else:
            response.status_int = 404
            return {'error': 'There is no orthography with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /orthographies/id: Delete an existing orthography.  Note that
        contributors can only update orthographies that are not used in the
        active application settings.
        """
        orthography = Session.query(Orthography).get(id)
        if orthography:
            appSet = h.getApplicationSettings()
            if session['user'].role == u'administrator' or orthography not in (
            appSet.storageOrthography, appSet.inputOrthography, appSet.outputOrthography):
                Session.delete(orthography)
                Session.commit()
                return orthography
            else:
                response.status = 403
                return {'error': u'Only administrators are permitted to delete orthographies that are used in the active application settings.'}
        else:
            response.status_int = 404
            return {'error': 'There is no orthography with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /orthographies/id: Return a JSON object representation of the orthography with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
        """
        orthography = Session.query(Orthography).get(id)
        if orthography:
            return orthography
        else:
            response.status_int = 404
            return {'error': 'There is no orthography with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /orthographies/id/edit: Return the data necessary to update an existing
        OLD orthography; here we return only the orthography and
        an empty JSON object.
        """
        orthography = Session.query(Orthography).get(id)
        if orthography:
            return {'data': {}, 'orthography': orthography}
        else:
            response.status_int = 404
            return {'error': 'There is no orthography with id %s' % id}


################################################################################
# Orthography Create & Update Functions
################################################################################

def createNewOrthography(data):
    """Create a new orthography model object given a data dictionary
    provided by the user (as a JSON object).
    """

    orthography = Orthography()
    orthography.name = h.normalize(data['name'])
    orthography.orthography = h.normalize(data['orthography'])
    orthography.lowercase = data['lowercase']
    orthography.initialGlottalStops = data['initialGlottalStops']
    orthography.datetimeModified = datetime.datetime.utcnow()
    return orthography

def updateOrthography(orthography, data):
    """Update the input orthography model object given a data dictionary
    provided by the user (as a JSON object).  If changed is not set to true in
    the course of attribute setting, then None is returned and no update occurs.
    """
    changed = False
    changed = h.setAttr(orthography, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(orthography, 'orthography', h.normalize(data['orthography']), changed)
    changed = h.setAttr(orthography, 'lowercase', data['lowercase'], changed)
    changed = h.setAttr(orthography, 'initialGlottalStops', data['initialGlottalStops'], changed)
    if changed:
        orthography.datetimeModified = datetime.datetime.utcnow()
        return orthography
    return changed