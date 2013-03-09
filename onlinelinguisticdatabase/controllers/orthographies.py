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

"""Contains the :class:`OrthographiesController` and its auxiliary functions.

.. module:: orthographies
   :synopsis: Contains the orthographies controller and its auxiliary functions.

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
from onlinelinguisticdatabase.lib.schemata import OrthographySchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Orthography

log = logging.getLogger(__name__)

class OrthographiesController(BaseController):
    """Generate responses to requests on orthography resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder('Orthography', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all orthography resources.

        :URL: ``GET /orthographies`` with optional query string parameters
            for ordering and pagination.
        :returns: a list of all orthography resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
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
        """Create a new orthography resource and return it.

        :URL: ``POST /orthographies``
        :request body: JSON object representing the orthography to create.
        :returns: the newly created orthography.

        """
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
        """Return the data necessary to create a new orthography.

        :URL: ``GET /orthographies/new``
        :returns: an empty dictionary

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update an orthography and return it.
        
        :URL: ``PUT /orthographies/id``
        :Request body: JSON object representing the orthography with updated attribute values.
        :param str id: the ``id`` value of the orthography to be updated.
        :returns: the updated orthography model.

        .. note::
        
            Contributors can only update orthographies that are not used in the
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
                    state = h.getStateObject(values)
                    state.id = id
                    result = schema.to_python(values, state)
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
        """Delete an existing orthography and return it.

        :URL: ``DELETE /orthographies/id``
        :param str id: the ``id`` value of the orthography to be deleted.
        :returns: the deleted orthography model.

        .. note::
        
            Contributors can only delete orthographies that are not used in the
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
        """Return an orthography.
        
        :URL: ``GET /orthographies/id``
        :param str id: the ``id`` value of the orthography to be returned.
        :returns: an orthography model object.

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
        """Return an orthography and the data needed to update it.

        :URL: ``GET /orthographies/edit``
        :param str id: the ``id`` value of the orthography that will be updated.
        :returns: a dictionary of the form::

                {"orthography": {...}, "data": {...}}

            where the value of the ``orthography`` key is a dictionary
            representation of the orthography and the value of the ``data`` key
            is an empty dictionary.

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
    """Create a new orthography.

    :param dict data: the data for the orthography to be created.
    :returns: an SQLAlchemy model object representing the orthography.

    """
    orthography = Orthography()
    orthography.name = h.normalize(data['name'])
    orthography.orthography = h.normalize(data['orthography'])
    orthography.lowercase = data['lowercase']
    orthography.initialGlottalStops = data['initialGlottalStops']
    orthography.datetimeModified = datetime.datetime.utcnow()
    return orthography

def updateOrthography(orthography, data):
    """Update an orthography.

    :param orthography: the orthography model to be updated.
    :param dict data: representation of the updated orthography.
    :returns: the updated orthography model or, if ``changed`` has not been set
        to ``True``, ``False``.

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