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

"""Contains the :class:`TagsController` and its auxiliary functions.

.. module:: tags
   :synopsis: Contains the tags controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import TagSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Tag

log = logging.getLogger(__name__)

class TagsController(BaseController):
    """Generate responses to requests on tag resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('Tag', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all tag resources.

        :URL: ``GET /tags`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all tag resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(Tag)
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
        """Create a new tag resource and return it.

        :URL: ``POST /tags``
        :request body: JSON object representing the tag to create.
        :returns: the newly created tag.

        """
        try:
            schema = TagSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            tag = create_new_tag(data)
            Session.add(tag)
            Session.commit()
            return tag
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
        """Return the data necessary to create a new tag.

        :URL: ``GET /tags/new``.
        :returns: an empty dictionary.

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a tag and return it.
        
        :URL: ``PUT /tags/id``
        :Request body: JSON object representing the tag with updated attribute values.
        :param str id: the ``id`` value of the tag to be updated.
        :returns: the updated tag model.

        """
        tag = Session.query(Tag).get(int(id))
        if tag:
            try:
                schema = TagSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                tag = update_tag(tag, data)
                # tag will be False if there are no changes (cf. update_tag).
                if tag:
                    Session.add(tag)
                    Session.commit()
                    return tag
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
            return {'error': 'There is no tag with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing tag and return it.

        :URL: ``DELETE /tags/id``
        :param str id: the ``id`` value of the tag to be deleted.
        :returns: the deleted tag model.

        """
        tag = Session.query(Tag).get(id)
        if tag:
            if tag.name not in (u'restricted', u'foreign word'):
                Session.delete(tag)
                Session.commit()
                return tag
            else:
                response.status_int = 403
                return {'error': 'The restricted and foreign word tags cannot be deleted.'}
        else:
            response.status_int = 404
            return {'error': 'There is no tag with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a tag.
        
        :URL: ``GET /tags/id``
        :param str id: the ``id`` value of the tag to be returned.
        :returns: a tag model object.

        """
        tag = Session.query(Tag).get(id)
        if tag:
            return tag
        else:
            response.status_int = 404
            return {'error': 'There is no tag with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a tag resource and the data needed to update it.

        :URL: ``GET /tags/edit``
        :param str id: the ``id`` value of the tag that will be updated.
        :returns: a dictionary of the form::

                {"tag": {...}, "data": {...}}

            where the value of the ``tag`` key is a dictionary representation of
            the tag and the value of the ``data`` key is an empty dictionary.

        """
        tag = Session.query(Tag).get(id)
        if tag:
            return {'data': {}, 'tag': tag}
        else:
            response.status_int = 404
            return {'error': 'There is no tag with id %s' % id}


################################################################################
# Tag Create & Update Functions
################################################################################

def create_new_tag(data):
    """Create a new tag.

    :param dict data: the data for the tag to be created.
    :returns: an SQLAlchemy model object representing the tag.

    """
    tag = Tag()
    tag.name = h.normalize(data['name'])
    tag.description = h.normalize(data['description'])
    tag.datetime_modified = datetime.datetime.utcnow()
    return tag

def update_tag(tag, data):
    """Update a tag.

    :param tag: the tag model to be updated.
    :param dict data: representation of the updated tag.
    :returns: the updated tag model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = tag.set_attr('name', h.normalize(data['name']), changed)
    changed = tag.set_attr('description', h.normalize(data['description']), changed)
    if changed:
        tag.datetime_modified = datetime.datetime.utcnow()
        return tag
    return changed
