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
import simplejson as json
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import SyntacticCategorySchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import SyntacticCategory
from forms import update_forms_containing_this_form_as_morpheme

log = logging.getLogger(__name__)

class SyntacticcategoriesController(BaseController):
    """Generate responses to requests on syntactic category resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('SyntacticCategory', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all syntactic category resources.

        :URL: ``GET /syntacticcategorys`` with optional query string parameters
            for ordering and pagination.
        :returns: a list of all syntactic category resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(SyntacticCategory)
            query = h.add_order_by(query, dict(request.GET), self.query_builder)
            return h.add_pagination(query, dict(request.GET))
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
            syntactic_category = create_new_syntactic_category(data)
            Session.add(syntactic_category)
            Session.commit()
            return syntactic_category
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
        return {'syntactic_category_types': h.syntactic_category_types}

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
        syntactic_category = Session.query(SyntacticCategory).get(int(id))
        if syntactic_category:
            try:
                old_name = syntactic_category.name
                schema = SyntacticCategorySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                syntactic_category = update_syntactic_category(syntactic_category, data)
                # syntactic_category will be False if there are no changes (cf. update_syntactic_category).
                if syntactic_category:
                    Session.add(syntactic_category)
                    Session.commit()
                    if syntactic_category.name != old_name:
                        update_forms_referencing_this_category(syntactic_category)
                    return syntactic_category
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
        syntactic_category = Session.query(SyntacticCategory).get(id)
        if syntactic_category:
            Session.delete(syntactic_category)
            Session.commit()
            update_forms_referencing_this_category(syntactic_category)
            return syntactic_category
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
        syntactic_category = Session.query(SyntacticCategory).get(id)
        if syntactic_category:
            return syntactic_category
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

                {"syntactic_category": {...}, "data": {...}}

            where the value of the ``syntactic_category`` key is a dictionary
            representation of the syntactic category and the value of the
            ``data`` key is a dictionary of valid syntactic category types as
            defined in :mod:`onlinelinguisticdatabase.lib.utils`.

        """
        syntactic_category = Session.query(SyntacticCategory).get(id)
        if syntactic_category:
            return {
                'data': {'syntactic_category_types': h.syntactic_category_types},
                'syntactic_category': syntactic_category
            }
        else:
            response.status_int = 404
            return {'error': 'There is no syntactic category with id %s' % id}


################################################################################
# SyntacticCategory Create & Update Functions
################################################################################

def create_new_syntactic_category(data):
    """Create a new syntactic category.

    :param dict data: the data for the syntactic category to be created.
    :returns: an SQLAlchemy model object representing the syntactic category.

    """
    syntactic_category = SyntacticCategory()
    syntactic_category.name = h.normalize(data['name'])
    syntactic_category.type = data['type']
    syntactic_category.description = h.normalize(data['description'])
    syntactic_category.datetime_modified = datetime.datetime.utcnow()
    return syntactic_category


def update_syntactic_category(syntactic_category, data):
    """Update a syntactic category.

    :param syntactic_category: the syntactic category model to be updated.
    :param dict data: representation of the updated syntactic category.
    :returns: the updated syntactic category model or, if ``changed`` has not
        been set to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = syntactic_category.set_attr('name', h.normalize(data['name']), changed)
    changed = syntactic_category.set_attr('type', h.normalize(data['type']), changed)
    changed = syntactic_category.set_attr('description', h.normalize(data['description']), changed)

    if changed:
        syntactic_category.datetime_modified = datetime.datetime.utcnow()
        return syntactic_category
    return changed


def update_forms_referencing_this_category(syntactic_category):
    """Update all forms that reference a syntactic category.

    :param syntactic_category: a syntactic category model object.
    :returns: ``None``
    
    .. note::
    
        This function is only called when a syntactic category is deleted or
        when its name is changed.

    """
    forms_of_this_category = syntactic_category.forms
    for form in forms_of_this_category:
        update_forms_containing_this_form_as_morpheme(form)
