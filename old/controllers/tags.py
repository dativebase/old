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
from old.lib.schemata import TagSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Tag

log = logging.getLogger(__name__)

class TagsController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Tag', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /tags: Return all tags."""
        try:
            query = Session.query(Tag)
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
        """POST /tags: Create a new tag."""
        try:
            schema = TagSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            tag = createNewTag(data)
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
        """GET /tags/new: Return the data necessary to create a new OLD
        tag.  NOTHING TO RETURN HERE ...
        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /tags/id: Update an existing tag."""
        tag = Session.query(Tag).get(int(id))
        if tag:
            try:
                schema = TagSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                tag = updateTag(tag, data)
                # tag will be False if there are no changes (cf. updateTag).
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
        """DELETE /tags/id: Delete an existing tag."""
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
        """GET /tags/id: Return a JSON object representation of the tag with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
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
        """GET /tags/id/edit: Return the data necessary to update an existing
        OLD tag; here we return only the tag and
        an empty JSON object.
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

def createNewTag(data):
    """Create a new tag model object given a data dictionary provided by the
    user (as a JSON object).
    """
    tag = Tag()
    tag.name = h.normalize(data['name'])
    tag.description = h.normalize(data['description'])
    tag.datetimeModified = datetime.datetime.utcnow()
    return tag

def updateTag(tag, data):
    """Update the input tag model object given a data dictionary provided by the
    user (as a JSON object).  If changed is not set to true in the course of
    attribute setting, then False is returned and no update occurs.
    """
    changed = False
    changed = h.setAttr(tag, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(tag, 'description', h.normalize(data['description']), changed)
    if changed:
        tag.datetimeModified = datetime.datetime.utcnow()
        return tag
    return changed