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
from old.lib.schemata import PhonologySchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Phonology

log = logging.getLogger(__name__)

class PhonologiesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Phonology', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """GET /phonologies: Return all phonologies."""
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
        """POST /phonologies: Create a new phonology."""
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
        """GET /phonologies/new: Return the data necessary to create a new OLD
        phonology.  NOTHING TO RETURN HERE ...
        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /phonologies/id: Update an existing phonology."""
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
        """DELETE /phonologies/id: Delete an existing phonology."""
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
        """GET /phonologies/id: Return a JSON object representation of the phonology with id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.
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
        """GET /phonologies/id/edit: Return the data necessary to update an existing
        OLD phonology; here we return only the phonology and
        an empty JSON object.
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
    """Create a new phonology model object given a data dictionary
    provided by the user (as a JSON object).
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

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updatePhonology function
# below.
CHANGED = None

def updatePhonology(phonology, data):
    """Update the input phonology model object given a data dictionary
    provided by the user (as a JSON object).  If CHANGED is not set to true in
    the course of attribute setting, then None is returned and no update occurs.
    """

    global CHANGED

    def setAttr(obj, name, value):
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            global CHANGED
            CHANGED = True

    # Unicode Data
    setAttr(phonology, 'name', h.normalize(data['name']))
    setAttr(phonology, 'description', h.normalize(data['description']))
    setAttr(phonology, 'script', h.normalize(data['script']))

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        phonology.modifier = session['user']
        phonology.datetimeModified = datetime.datetime.utcnow()
        return phonology
    return CHANGED
