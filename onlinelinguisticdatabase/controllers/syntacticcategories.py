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
from onlinelinguisticdatabase.lib.schemata import SyntacticCategorySchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import SyntacticCategory
from forms import updateFormsContainingThisFormAsMorpheme

log = logging.getLogger(__name__)

class SyntacticcategoriesController(BaseController):

    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('SyntacticCategory', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /syntacticcategories: Return all syntactic categories."""
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
        """POST /syntacticcategories: Create a new syntactic category."""
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
        """GET /syntacticcategories/new: Return the data necessary to create a new OLD
        syntactic category.  Here we simply return the list of syntactic category
        types defined in lib/utils.
        """
        return {'syntacticCategoryTypes': h.syntacticCategoryTypes}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /syntacticcategories/id: Update an existing syntactic category."""
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
        """DELETE /syntacticcategories/id: Delete an existing syntactic category."""
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
        """GET /syntacticcategories/id: Return a JSON object representation of
        the syntactic category with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
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
        """GET /syntacticcategories/id/edit: Return the data necessary to update an existing
        OLD syntactic category; here we return only the syntactic category and
        the list of syntactic category types defined in lib/utils.
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
    """Create a new syntactic category model object given a data dictionary
    provided by the user (as a JSON object).
    """

    syntacticCategory = SyntacticCategory()
    syntacticCategory.name = h.normalize(data['name'])
    syntacticCategory.type = data['type']
    syntacticCategory.description = h.normalize(data['description'])
    syntacticCategory.datetimeModified = datetime.datetime.utcnow()
    return syntacticCategory


def updateSyntacticCategory(syntacticCategory, data):
    """Update the input syntactic category model object given a data dictionary
    provided by the user (as a JSON object).  If changed is not set to true in
    the course of attribute setting, then None is returned and no update occurs.
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
    formsOfThisCategory = syntacticCategory.forms
    for form in formsOfThisCategory:
        updateFormsContainingThisFormAsMorpheme(form)