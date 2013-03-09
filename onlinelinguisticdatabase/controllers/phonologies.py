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

"""Contains the :class:`PhonologiesController` and its auxiliary functions.

.. module:: phonologies
   :synopsis: Contains the phonologies controller and its auxiliary functions.

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
from onlinelinguisticdatabase.lib.schemata import PhonologySchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Phonology

log = logging.getLogger(__name__)

class PhonologiesController(BaseController):
    """Generate responses to requests on phonology resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder('Phonology', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all phonology resources.

        :URL: ``GET /phonologies`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all phonology resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerloadPhonology(Session.query(Phonology))
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
        """Create a new phonology resource and return it.

        :URL: ``POST /phonologies``
        :request body: JSON object representing the phonology to create.
        :returns: the newly created phonology.

        """
        try:
            schema = PhonologySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            phonology = createNewPhonology(data)
            Session.add(phonology)
            Session.commit()
            return phonology
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
        """Return the data necessary to create a new phonology.

        :URL: ``GET /phonologies/new``.
        :returns: an empty dictionary.

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a phonology and return it.
        
        :URL: ``PUT /phonologies/id``
        :Request body: JSON object representing the phonology with updated attribute values.
        :param str id: the ``id`` value of the phonology to be updated.
        :returns: the updated phonology model.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(int(id))
        if phonology:
            try:
                schema = PhonologySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                phonology = updatePhonology(phonology, data)
                # phonology will be False if there are no changes (cf. updatePhonology).
                if phonology:
                    Session.add(phonology)
                    Session.commit()
                    return phonology
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
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing phonology and return it.

        :URL: ``DELETE /phonologies/id``
        :param str id: the ``id`` value of the phonology to be deleted.
        :returns: the deleted phonology model.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(id)
        if phonology:
            Session.delete(phonology)
            Session.commit()
            return phonology
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a phonology.
        
        :URL: ``GET /phonologies/id``
        :param str id: the ``id`` value of the phonology to be returned.
        :returns: a phonology model object.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(id)
        if phonology:
            return phonology
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a phonology and the data needed to update it.

        :URL: ``GET /phonologies/edit``
        :param str id: the ``id`` value of the phonology that will be updated.
        :returns: a dictionary of the form::

                {"phonology": {...}, "data": {...}}

            where the value of the ``phonology`` key is a dictionary
            representation of the phonology and the value of the ``data`` key
            is an empty dictionary.

        """
        phonology = h.eagerloadPhonology(Session.query(Phonology)).get(id)
        if phonology:
            return {'data': {}, 'phonology': phonology}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}


################################################################################
# Phonology Create & Update Functions
################################################################################

def createNewPhonology(data):
    """Create a new phonology.

    :param dict data: the data for the phonology to be created.
    :returns: an SQLAlchemy model object representing the phonology.

    """
    phonology = Phonology()
    phonology.name = h.normalize(data['name'])
    phonology.description = h.normalize(data['description'])
    phonology.script = h.normalize(data['script'])  # normalize or not?

    phonology.enterer = session['user']
    phonology.modifier = session['user']

    now = datetime.datetime.utcnow()
    phonology.datetimeModified = now
    phonology.datetimeEntered = now
    return phonology

def updatePhonology(phonology, data):
    """Update a phonology.

    :param page: the phonology model to be updated.
    :param dict data: representation of the updated phonology.
    :returns: the updated phonology model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = h.setAttr(phonology, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(phonology, 'description', h.normalize(data['description']), changed)
    changed = h.setAttr(phonology, 'script', h.normalize(data['script']), changed)

    if changed:
        phonology.modifier = session['user']
        phonology.datetimeModified = datetime.datetime.utcnow()
        return phonology
    return changed
