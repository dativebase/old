"""The OLD reifies form searches.

create a search:
    {
        'filterExpression': [...],
        'orderBy': [<model>, <attribute>]

Problems with searching:

1. Standardly, SQLite provides no way of escaping the underscore and the percent
   sign in LIKE queries.  Using the "ESCAPE clause" (e.g., SELECT * FROM form
   WHERE transcription LIKE '%\_%' ESCAPE '\') works, but how can it be done
   from SQLAlchemy?
2. By default, SQLite LIKE searches are case-insensitive.  This can be fixed by
   using a PRAGMA statement (e.g., PRAGMA case_sensitive_like = true;), but,
   again, how can it be done from SQLAlchemy?
3. By default, MySQL LIKE and REGEXP searches are case-insensitive ...

"""

import logging
import datetime
import re
import simplejson as json

from pylons import config, request, response, session, app_globals
from pylons.decorators.rest import restrict
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError

from old.lib.base import BaseController
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError

log = logging.getLogger(__name__)


class FormsearchesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder()

    def index(self):
        """GET /formsearches: Retrieve all form searches in the collection."""
        #return str(config['pylons.paths'])
        return str('<br />'.join(config.keys()))
        #return config['sqlalchemy.url']

    @restrict('POST')
    @h.authenticate
    def create(self):
        """POST /formsearches: Create a new form search."""

        response.content_type = 'application/json'
        try:
            jsonQuery = unicode(request.body, request.charset)
            pythonQuery = json.loads(jsonQuery)
            SQLAQuery = self.queryBuilder.getSQLAQuery(pythonQuery)
            forms = SQLAQuery.all()
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except OLDSearchParseError, e:
            response.status_int = 400
            return json.dumps({'errors': e.unpack_errors()})
        # SQLAQueryBuilder should have captured these exceptions (and packed
        # them into an OLDSearchParseError) or sidestepped them, but here we'll
        # handle any that got past -- just in case.
        except (OperationalError, AttributeError, InvalidRequestError, RuntimeError):
            response.status_int = 400
            return json.dumps({'error':
                u'The specified search parameters generated an invalid database query'})
        else:
            return json.dumps(forms, cls=h.JSONOLDEncoder)

    def new(self):
        """GET /formsearches/new: Return the data needed to create a new form search."""
        # url('new_formsearch')

    def delete(self, id):
        """DELETE /formsearches/id: Delete an existing form search."""
        pass

    def show(self, id):
        """GET /formsearches/id: Show a specific form search."""
        # url('formsearch', id=ID)

    def edit(self, id):
        """GET /formsearches/id/edit: Return the data needed to edit an existing
        form search.
        """
        # url('edit_formsearch', id=ID)
