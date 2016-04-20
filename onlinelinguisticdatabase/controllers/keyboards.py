# Copyright 2016 Joel Dunham
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

"""Contains the :class:`KeyboardsController` and its auxiliary functions.

.. module:: keyboards
   :synopsis: Contains the keyboards controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, config, session
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import KeyboardSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Keyboard

log = logging.getLogger(__name__)

class KeyboardsController(BaseController):
    """Generate responses to requests on keyboard resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::

       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('Keyboard', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of keyboard resources matching the input
        JSON query.

        :URL: ``SEARCH /keyboards``
          (or ``POST /keyboards/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        """
        try:
            json_search_params = unicode(request.body, request.charset)
            python_search_params = json.loads(json_search_params)
            query = self.query_builder.get_SQLA_query(
                python_search_params.get('query'))
            return h.add_pagination(query,
                python_search_params.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except:
            response.status_int = 400
            return {'error': (u'The specified search parameters generated an'
                ' invalid database query')}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """Return the data necessary to search the keyboard resources.

        :URL: ``GET /keyboards/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """

        return {'search_parameters':
            h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all keyboard resources.

        :URL: ``GET /keyboards`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all keyboard resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for
           the query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(Keyboard)
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
        """Create a new keyboard resource and return it.

        :URL: ``POST /keyboards``
        :request body: JSON object representing the keyboard to create.
        :returns: the newly created keyboard.

        """
        try:
            schema = KeyboardSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            keyboard = create_new_keyboard(data)
            Session.add(keyboard)
            Session.commit()
            return keyboard
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
        """Return the data necessary to create a new keyboard.

        :URL: ``GET /keyboards/new``.
        :returns: an empty dictionary.

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a keyboard and return it.

        :URL: ``PUT /keyboards/id``
        :Request body: JSON object representing the keyboard with updated
            attribute values.
        :param str id: the ``id`` value of the keyboard to be updated.
        :returns: the updated keyboard model.

        """
        keyboard = Session.query(Keyboard).get(int(id))
        if keyboard:
            try:
                schema = KeyboardSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                keyboard = update_keyboard(keyboard, data)
                # keyboard will be False if there are no changes (cf.
                # update_keyboard).
                if keyboard:
                    Session.add(keyboard)
                    Session.commit()
                    return keyboard
                else:
                    response.status_int = 400
                    return {'error': (u'The update request failed because the'
                        u' submitted data were not new.')}
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no keyboard with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing keyboard and return it.

        :URL: ``DELETE /keyboards/id``
        :param str id: the ``id`` value of the keyboard to be deleted.
        :returns: the deleted keyboard model.

        """
        keyboard = Session.query(Keyboard).get(id)
        if keyboard:
            Session.delete(keyboard)
            Session.commit()
            return keyboard
        else:
            response.status_int = 404
            return {'error': 'There is no keyboard with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a keyboard.

        :URL: ``GET /keyboards/id``
        :param str id: the ``id`` value of the keyboard to be returned.
        :returns: a keyboard model object.

        """
        keyboard = Session.query(Keyboard).get(id)
        if keyboard:
            return keyboard
        else:
            response.status_int = 404
            return {'error': 'There is no keyboard with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a keyboard resource and the data needed to update it.

        :URL: ``GET /keyboards/edit``
        :param str id: the ``id`` value of the keyboard that will be updated.
        :returns: a dictionary of the form::

                {"keyboard": {...}, "data": {...}}

            where the value of the ``keyboard`` key is a dictionary
            representation of the keyboard and the value of the ``data`` key is
            an empty dictionary.

        """
        keyboard = Session.query(Keyboard).get(id)
        if keyboard:
            return {'data': {}, 'keyboard': keyboard}
        else:
            response.status_int = 404
            return {'error': 'There is no keyboard with id %s' % id}


################################################################################
# Keyboard Create & Update Functions
################################################################################

def create_new_keyboard(data):
    """Create a new keyboard.

    :param dict data: the data for the keyboard to be created.
    :returns: an SQLAlchemy model object representing the keyboard.

    """
    keyboard = Keyboard()
    keyboard.name = h.normalize(data['name'])
    keyboard.description = h.normalize(data['description'])
    keyboard.keyboard = h.normalize(data['keyboard'])

    # OLD-generated Data
    keyboard.datetime_entered = keyboard.datetime_modified = h.now()
    keyboard.enterer = keyboard.modifier = session['user']

    return keyboard

def update_keyboard(keyboard, data):
    """Update a keyboard.

    :param keyboard: the keyboard model to be updated.
    :param dict data: representation of the updated keyboard.
    :returns: the updated keyboard model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = keyboard.set_attr('name', h.normalize(data['name']), changed)
    changed = keyboard.set_attr('description',
        h.normalize(data['description']), changed)
    changed = keyboard.set_attr('keyboard',
        h.normalize(data['keyboard']), changed)
    if changed:
        keyboard.datetime_modified = h.now()
        session['user'] = Session.merge(session['user'])
        keyboard.modifier = session['user']
        return keyboard
    return changed

