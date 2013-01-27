import logging
import datetime
import re
import simplejson as json
from uuid import uuid4

from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc

from old.lib.base import BaseController
from old.lib.schemata import FormIdsSchemaNullable
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Form, User

log = logging.getLogger(__name__)

class RememberedformsController(BaseController):
    """A pseudo-REST-ful resource.  Remembered forms are stored in the userform
    many-to-many table (cf. model/user.py) which defines the contents of
    User(id).rememberedForms (and Form(id).memorizers).  A user's remembered
    forms are not affected by requests to the user resource.  Instead, the
    rememberedforms resource handles modification, retrieval and search of a
    user's remembered forms.

    Here is the API:

    GET /rememberedforms/id -- return all forms remembered by the user with
    id=id.  Action: show(id).

    UPDATE /rememberedforms/id -- set the user with id=id's remembered forms to
    the set of forms corresponding to the JSON array of form ids sent in the
    request body; (accomplishes CUD; same as controllers/forms.remember).
    Action: update(id).

    SEARCH /rememberedforms/id -- return all forms remembered by the user with
    id=id and which match the JSON search filter passed in the request body.
    Action: search(id)
    """

    queryBuilder = SQLAQueryBuilder(config=config)

    @h.OLDjsonify
    @h.authenticate
    @restrict('GET')
    def show(self, id):
        """Return a JSON array of the forms remembered by the user with id=id.
        Note that any authenticated user is authorized to access this array.
        Restricted forms are filtered from the array on a per-user basis.
        """
        user = Session.query(User).get(id)
        if user:
            try:
                query = Session.query(Form).filter(Form.memorizers.contains(user))
                query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
                query = h.filterRestrictedModels('Form', query)
                return h.addPagination(query, dict(request.GET))
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}

    @h.OLDjsonify
    @h.authenticate
    @restrict('PUT')
    @h.authorize(['administrator', 'contributor', 'viewer'], None, True)
    def update(self, id):
        """Set the user with id=id's rememberedForms to the forms referenced by
        the array of form ids passed in the request body.  This action is very
        similar to the remember action in the forms controller, the difference
        being that remember only appends forms to the logged in user's remembered
        forms list while the present action can modify an arbitrary user's
        remembered forms without restriction (i.e., clear, append, remove).
        Admins can update any user's remembered forms; non-admins can only
        update their own.
        """
        user = Session.query(User).get(id)
        if user:
            try:
                schema = FormIdsSchemaNullable
                values = json.loads(unicode(request.body, request.charset))
                data = schema.to_python(values)
                forms = [f for f in data['forms'] if f]
                accessible = h.userIsAuthorizedToAccessModel
                unrestrictedUsers = h.getUnrestrictedUsers()
                unrestrictedForms = [f for f in forms
                                     if accessible(user, f, unrestrictedUsers)]
                if set(user.rememberedForms) != set(unrestrictedForms):
                    user.rememberedForms = unrestrictedForms
                    user.datetimeModified = h.now()
                    Session.commit()
                    return user.rememberedForms
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
            return {'error': 'There is no user with id %s' % id}

    @h.OLDjsonify
    @restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self, id):
        """SEARCH /forms: Return all forms in the user with id=id's remembered
        forms that match the filter passed as JSON in the request body.  Note:
        POST /rememberedForms/id/search also routes to this action.

        The request body must be a JSON object with a 'query' attribute; a
        'paginator' attribute is optional.  The 'query' object is passed to the
        getSQLAQuery() method of an SQLAQueryBuilder instance and an SQLA query
        is returned or an error is raised.  The 'query' object requires a
        'filter' attribute; an 'orderBy' attribute is optional.
        """
        user = Session.query(User).get(id)
        if user:
            try:
                jsonSearchParams = unicode(request.body, request.charset)
                pythonSearchParams = json.loads(jsonSearchParams)
                query = self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query'))
                query = query.filter(Form.memorizers.contains(user))
                query = h.filterRestrictedModels('Form', query)
                return h.addPagination(query, pythonSearchParams.get('paginator'))
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except (OLDSearchParseError, Invalid), e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
            # SQLAQueryBuilder should have captured these exceptions (and packed
            # them into an OLDSearchParseError) or sidestepped them, but here we'll
            # handle any that got past -- just in case.
            except (OperationalError, AttributeError, InvalidRequestError, RuntimeError):
                response.status_int = 400
                return {'error': u'The specified search parameters generated an invalid database query'}
        else:
            response.status_int = 404
            return {'error': 'There is no user with id %s' % id}
