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

"""Contains the :class:`SyntacticcategoriesController` and its auxiliary functions.

.. module:: syntacticcategories
   :synopsis: Contains the syntactic category controller and its auxiliary functions.

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
from onlinelinguisticdatabase.lib.schemata import SyntacticCategorySchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import SyntacticCategory
from forms import updateFormsContainingThisFormAsMorpheme

log = logging.getLogger(__name__)

class SyntacticcategoriesController(BaseController):
    """Generate responses to requests on syntactic category resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    queryBuilder = SQLAQueryBuilder('SyntacticCategory', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all syntactic category resources.

        :URL: ``GET /syntacticcategorys`` with optional query string parameters
            for ordering and pagination.
        :returns: a list of all syntactic category resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(SyntacticCategory)
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
        """Create a new syntactic category resource and return it.

        :URL: ``POST /syntacticcategorys``
        :request body: JSON object representing the syntactic category to create.
        :returns: the newly created syntactic category.

        """
        try:
            schema = SyntacticCategorySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            syntacticCategory = createNewSyntacticCategory(data)
            Session.add(syntacticCategory)
            Session.commit()
            return syntacticCategory
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
        """Return the data necessary to create a new syntactic category.

        :URL: ``GET /syntacticcategorys/new``.
        :returns: a dictionary containing the valid syntactic category types as
            defined in :mod:`onlinelinguisticdatabase.lib.utils`.

        """
        return {'syntacticCategoryTypes': h.syntacticCategoryTypes}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a syntactic category and return it.
        
        :URL: ``PUT /syntacticcategorys/id``
        :Request body: JSON object representing the syntactic category with updated attribute values.
        :param str id: the ``id`` value of the syntactic category to be updated.
        :returns: the updated syntactic category model.

        """
        syntacticCategory = Session.query(SyntacticCategory).get(int(id))
        if syntacticCategory:
            try:
                oldName = syntacticCategory.name
                schema = SyntacticCategorySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                syntacticCategory = updateSyntacticCategory(syntacticCategory, data)
                # syntacticCategory will be False if there are no changes (cf. updateSyntacticCategory).
                if syntacticCategory:
                    Session.add(syntacticCategory)
                    Session.commit()
                    if syntacticCategory.name != oldName:
                        updateFormsReferencingThisCategory(syntacticCategory)
                    return syntacticCategory
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
            return {'error': 'There is no syntactic category with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing syntactic category and return it.

        :URL: ``DELETE /syntacticcategorys/id``
        :param str id: the ``id`` value of the syntactic category to be deleted.
        :returns: the deleted syntactic category model.

        """
        syntacticCategory = Session.query(SyntacticCategory).get(id)
        if syntacticCategory:
            Session.delete(syntacticCategory)
            Session.commit()
            updateFormsReferencingThisCategory(syntacticCategory)
            return syntacticCategory
        else:
            response.status_int = 404
            return {'error': 'There is no syntactic category with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a syntactic category.
        
        :URL: ``GET /syntacticcategorys/id``
        :param str id: the ``id`` value of the syntactic category to be returned.
        :returns: a syntactic category model object.

        """
        syntacticCategory = Session.query(SyntacticCategory).get(id)
        if syntacticCategory:
            return syntacticCategory
        else:
            response.status_int = 404
            return {'error': 'There is no syntactic category with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a syntactic category resource and the data needed to update it.

        :URL: ``GET /syntacticcategorys/edit``
        :param str id: the ``id`` value of the syntactic category that will be updated.
        :returns: a dictionary of the form::

                {"syntacticCategory": {...}, "data": {...}}

            where the value of the ``syntacticCategory`` key is a dictionary
            representation of the syntactic category and the value of the
            ``data`` key is a dictionary of valid syntactic category types as
            defined in :mod:`onlinelinguisticdatabase.lib.utils`.

        """
        syntacticCategory = Session.query(SyntacticCategory).get(id)
        if syntacticCategory:
            return {
                'data': {'syntacticCategoryTypes': h.syntacticCategoryTypes},
                'syntacticCategory': syntacticCategory
            }
        else:
            response.status_int = 404
            return {'error': 'There is no syntactic category with id %s' % id}


################################################################################
# SyntacticCategory Create & Update Functions
################################################################################

def createNewSyntacticCategory(data):
    """Create a new syntactic category.

    :param dict data: the data for the syntactic category to be created.
    :returns: an SQLAlchemy model object representing the syntactic category.

    """
    syntacticCategory = SyntacticCategory()
    syntacticCategory.name = h.normalize(data['name'])
    syntacticCategory.type = data['type']
    syntacticCategory.description = h.normalize(data['description'])
    syntacticCategory.datetimeModified = datetime.datetime.utcnow()
    return syntacticCategory


def updateSyntacticCategory(syntacticCategory, data):
    """Update a syntactic category.

    :param syntacticCategory: the syntactic category model to be updated.
    :param dict data: representation of the updated syntactic category.
    :returns: the updated syntactic category model or, if ``changed`` has not
        been set to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = h.setAttr(syntacticCategory, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(syntacticCategory, 'type', h.normalize(data['type']), changed)
    changed = h.setAttr(syntacticCategory, 'description', h.normalize(data['description']), changed)

    if changed:
        syntacticCategory.datetimeModified = datetime.datetime.utcnow()
        return syntacticCategory
    return changed


def updateFormsReferencingThisCategory(syntacticCategory):
    """Update all forms that reference a syntactic category.

    :param syntacticCategory: a syntactic category model object.
    :returns: ``None``
    
    .. note::
    
        This function is only called when a syntactic category is deleted or
        when its name is changed.

    """
    formsOfThisCategory = syntacticCategory.forms
    for form in formsOfThisCategory:
        updateFormsContainingThisFormAsMorpheme(form)