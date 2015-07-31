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

"""Contains the :class:`SpeakersController` and its auxiliary functions.

.. module:: speakers
   :synopsis: Contains the speakers controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import SpeakerSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Speaker

log = logging.getLogger(__name__)

class SpeakersController(BaseController):
    """Generate responses to requests on speaker resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('Speaker', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all speaker resources.

        :URL: ``GET /speakers`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all speaker resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(Speaker)
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
        """Create a new speaker resource and return it.

        :URL: ``POST /speakers``
        :request body: JSON object representing the speaker to create.
        :returns: the newly created speaker.

        """
        try:
            schema = SpeakerSchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            speaker = create_new_speaker(data)
            Session.add(speaker)
            Session.commit()
            return speaker
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
        """Return the data necessary to create a new speaker.

        :URL: ``GET /speakers/new``.
        :returns: an empty dictionary.

        """
        return {'markup_languages': h.markup_languages}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a speaker and return it.
        
        :URL: ``PUT /speakers/id``
        :Request body: JSON object representing the speaker with updated attribute values.
        :param str id: the ``id`` value of the speaker to be updated.
        :returns: the updated speaker model.

        """
        speaker = Session.query(Speaker).get(int(id))
        if speaker:
            try:
                schema = SpeakerSchema()
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                speaker = update_speaker(speaker, data)
                # speaker will be False if there are no changes (cf. update_speaker).
                if speaker:
                    Session.add(speaker)
                    Session.commit()
                    return speaker
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
            return {'error': 'There is no speaker with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing speaker and return it.

        :URL: ``DELETE /speakers/id``
        :param str id: the ``id`` value of the speaker to be deleted.
        :returns: the deleted speaker model.

        """
        speaker = Session.query(Speaker).get(id)
        if speaker:
            Session.delete(speaker)
            Session.commit()
            return speaker
        else:
            response.status_int = 404
            return {'error': 'There is no speaker with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a speaker.
        
        :URL: ``GET /speakers/id``
        :param str id: the ``id`` value of the speaker to be returned.
        :returns: a speaker model object.

        """
        speaker = Session.query(Speaker).get(id)
        if speaker:
            return speaker
        else:
            response.status_int = 404
            return {'error': 'There is no speaker with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a speaker resource and the data needed to update it.

        :URL: ``GET /speakers/edit``
        :param str id: the ``id`` value of the speaker that will be updated.
        :returns: a dictionary of the form::

                {"speaker": {...}, "data": {...}}

            where the value of the ``speaker`` key is a dictionary
            representation of the speaker and the value of the ``data`` key
            is an empty dictionary.

        TODO: implement a `get_new_speaker_data` function here, similar to that
        defined in controllers/user.py so that GET params can effect what data
        are returned.

        """
        speaker = Session.query(Speaker).get(id)
        if speaker:
            return {
                'data': {'markup_languages': h.markup_languages},
                'speaker': speaker
            }
        else:
            response.status_int = 404
            return {'error': 'There is no speaker with id %s' % id}


################################################################################
# Speaker Create & Update Functions
################################################################################

def create_new_speaker(data):
    """Create a new speaker.

    :param dict data: the data for the speaker to be created.
    :returns: an SQLAlchemy model object representing the speaker.

    """
    speaker = Speaker()
    speaker.first_name = h.normalize(data['first_name'])
    speaker.last_name = h.normalize(data['last_name'])
    speaker.dialect = h.normalize(data['dialect'])
    speaker.page_content = h.normalize(data['page_content'])
    speaker.datetime_modified = datetime.datetime.utcnow()
    speaker.markup_language = h.normalize(data['markup_language'])
    speaker.html = h.get_HTML_from_contents(speaker.page_content, speaker.markup_language)
    return speaker


def update_speaker(speaker, data):
    """Update a speaker.

    :param speaker: the speaker model to be updated.
    :param dict data: representation of the updated speaker.
    :returns: the updated speaker model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False

    # Unicode Data
    changed = speaker.set_attr('first_name', h.normalize(data['first_name']), changed)
    changed = speaker.set_attr('last_name', h.normalize(data['last_name']), changed)
    changed = speaker.set_attr('dialect', h.normalize(data['dialect']), changed)
    changed = speaker.set_attr('page_content', h.normalize(data['page_content']), changed)
    changed = speaker.set_attr('markup_language', h.normalize(data['markup_language']), changed)
    changed = speaker.set_attr('html',
                        h.get_HTML_from_contents(speaker.page_content, speaker.markup_language),
                        changed)

    if changed:
        speaker.datetime_modified = datetime.datetime.utcnow()
        return speaker
    return changed
