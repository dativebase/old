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
from old.lib.schemata import SourceSchema
import old.lib.helpers as h
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from old.model.meta import Session
from old.model import Source
from old.lib.bibtex import entryTypes

log = logging.getLogger(__name__)

class SourcesController(BaseController):
    """REST Controller styled on the Atom Publishing Protocol"""

    queryBuilder = SQLAQueryBuilder('Source', config=config)

    @h.OLDjsonify
    @restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """SEARCH /sources: Return all sources matching the filter passed as JSON in
        the request body.  Note: POST /sources/search also routes to this action.
        The request body must be a JSON object with a 'query' attribute; a
        'paginator' attribute is optional.  The 'query' object is passed to the
        getSQLAQuery() method of an SQLAQueryBuilder instance and an SQLA query
        is returned or an error is raised.  The 'query' object requires a
        'filter' attribute; an 'orderBy' attribute is optional.
        """
        #for attr in dir(self.queryBuilder):
        #    log.warn('self.queryBuilder.%s = %s' % (attr, getattr(self.queryBuilder, attr)))
        try:
            jsonSearchParams = unicode(request.body, request.charset)
            pythonSearchParams = json.loads(jsonSearchParams)
            query = self.queryBuilder.getSQLAQuery(pythonSearchParams.get('query'))
            #log.warn(h.compile_query(query))
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

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def index(self):
        """GET /sources: Return all sources."""
        try:
            query = Session.query(Source)
            query = h.addOrderBy(query, dict(request.GET), self.queryBuilder)
            return h.addPagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.OLDjsonify
    @restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """POST /sources: Create a new source."""
        try:
            schema = SourceSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.getStateObject(values)
            data = schema.to_python(values, state)
            source = createNewSource(data)
            Session.add(source)
            Session.commit()
            return source
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """GET /sources/new: Return the data necessary to create a new OLD source.
        All that is returned here is the list of valid BibTeX entry types.  GET
        params are ignored.
        """
        return {'types': sorted(entryTypes.keys())}

    @h.OLDjsonify
    @restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """PUT /sources/id: Update an existing source."""
        source = Session.query(Source).get(int(id))
        if source:
            try:
                schema = SourceSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                source = updateSource(source, data)
                # source will be False if there are no changes (cf. updateSource).
                if source:
                    Session.add(source)
                    Session.commit()
                    return source
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
            return {'error': 'There is no source with id %s' % id}

    @h.OLDjsonify
    @restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """DELETE /sources/id: Delete an existing source."""
        source = Session.query(Source).get(id)
        if source:
            Session.delete(source)
            Session.commit()
            return source
        else:
            response.status_int = 404
            return {'error': 'There is no source with id %s' % id}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    def show(self, id):
        """GET /sources/id: Return a JSON object representation of the source with
        id=id.

        If the id is invalid, the header will contain a 404 status int and a
        JSON object will be returned.  If the id is unspecified, then Routes
        will put a 404 status int into the header and the default 404 JSON
        object defined in controllers/error.py will be returned.

        A source associated to a restricted file will still return a subset of the
        restricted file's metadata.  However, restricted users will be unable to
        retrieve the binary content of the file because of the authorization logic
        the retrieve action of the files controller.
        """
        source = Session.query(Source).get(id)
        if source:
            return source
        else:
            response.status_int = 404
            return {'error': 'There is no source with id %s' % id}

    @h.OLDjsonify
    @restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """GET /sources/id/edit: Return the data necessary to update an existing
        OLD source, i.e., the source's properties and the list of entry types.
        """
        source = Session.query(Source).get(id)
        if source:
            return {'data': {'types': sorted(entryTypes.keys())}, 'source': source}
        else:
            response.status_int = 404
            return {'error': 'There is no source with id %s' % id}


################################################################################
# Source Create & Update Functions
################################################################################

def createNewSource(data):
    """Create a new source model object given a data dictionary provided by the
    user (as a JSON object).
    """

    source = Source()
    source.type = h.normalize(data['type'])
    source.key = h.normalize(data['key'])
    source.address = h.normalize(data['address'])
    source.annote = h.normalize(data['annote'])
    source.author = h.normalize(data['author'])
    source.booktitle = h.normalize(data['booktitle'])
    source.chapter = h.normalize(data['chapter'])
    source.crossref = h.normalize(data['crossref'])
    source.edition = h.normalize(data['edition'])
    source.editor = h.normalize(data['editor'])
    source.howpublished = h.normalize(data['howpublished'])
    source.institution = h.normalize(data['institution'])
    source.journal = h.normalize(data['journal'])
    source.keyField = h.normalize(data['keyField'])
    source.month = h.normalize(data['month'])
    source.note = h.normalize(data['note'])
    source.number = h.normalize(data['number'])
    source.organization = h.normalize(data['organization'])
    source.pages = h.normalize(data['pages'])
    source.publisher = h.normalize(data['publisher'])
    source.school = h.normalize(data['school'])
    source.series = h.normalize(data['series'])
    source.title = h.normalize(data['title'])
    source.typeField = h.normalize(data['typeField'])
    source.url = data['url']
    source.volume = h.normalize(data['volume'])
    source.year = data['year']
    source.affiliation = h.normalize(data['affiliation'])
    source.abstract = h.normalize(data['abstract'])
    source.contents = h.normalize(data['contents'])
    source.copyright = h.normalize(data['copyright'])
    source.ISBN = h.normalize(data['ISBN'])
    source.ISSN = h.normalize(data['ISSN'])
    source.keywords = h.normalize(data['keywords'])
    source.language = h.normalize(data['language'])
    source.location = h.normalize(data['location'])
    source.LCCN = h.normalize(data['LCCN'])
    source.mrnumber = h.normalize(data['mrnumber'])
    source.price = h.normalize(data['price'])
    source.size = h.normalize(data['size'])

    # Many-to-one: file
    if data['file']:
        source.file = data['file']

    # OLD-generated Data
    source.datetimeModified = datetime.datetime.utcnow()

    return source

# Global CHANGED variable keeps track of whether an update request should
# succeed.  This global may only be used/changed in the updateForm function
# below.
CHANGED = None

def updateSource(source, data):
    """Update the input Source model object given a data dictionary provided by
    the user (as a JSON object).  If CHANGED is not set to true in the course
    of attribute setting, then None is returned and no update occurs.
    """

    global CHANGED

    def setAttr(obj, name, value):
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            global CHANGED
            CHANGED = True

    # Unicode Data
    setAttr(source, 'type', h.normalize(data['type']))
    setAttr(source, 'key', h.normalize(data['key']))
    setAttr(source, 'address', h.normalize(data['address']))
    setAttr(source, 'annote', h.normalize(data['annote']))
    setAttr(source, 'author', h.normalize(data['author']))
    setAttr(source, 'booktitle', h.normalize(data['booktitle']))
    setAttr(source, 'chapter', h.normalize(data['chapter']))
    setAttr(source, 'crossref', h.normalize(data['crossref']))
    setAttr(source, 'edition', h.normalize(data['edition']))
    setAttr(source, 'editor', h.normalize(data['editor']))
    setAttr(source, 'howpublished', h.normalize(data['howpublished']))
    setAttr(source, 'institution', h.normalize(data['institution']))
    setAttr(source, 'journal', h.normalize(data['journal']))
    setAttr(source, 'keyField', h.normalize(data['keyField']))
    setAttr(source, 'month', h.normalize(data['month']))
    setAttr(source, 'note', h.normalize(data['note']))
    setAttr(source, 'number', h.normalize(data['number']))
    setAttr(source, 'organization', h.normalize(data['organization']))
    setAttr(source, 'pages', h.normalize(data['pages']))
    setAttr(source, 'publisher', h.normalize(data['publisher']))
    setAttr(source, 'school', h.normalize(data['school']))
    setAttr(source, 'series', h.normalize(data['series']))
    setAttr(source, 'title', h.normalize(data['title']))
    setAttr(source, 'typeField', h.normalize(data['typeField']))
    setAttr(source, 'url', data['url'])
    setAttr(source, 'volume', h.normalize(data['volume']))
    setAttr(source, 'year', data['year'])
    setAttr(source, 'affiliation', h.normalize(data['affiliation']))
    setAttr(source, 'abstract', h.normalize(data['abstract']))
    setAttr(source, 'contents', h.normalize(data['contents']))
    setAttr(source, 'copyright', h.normalize(data['copyright']))
    setAttr(source, 'ISBN', h.normalize(data['ISBN']))
    setAttr(source, 'ISSN', h.normalize(data['ISSN']))
    setAttr(source, 'keywords', h.normalize(data['keywords']))
    setAttr(source, 'language', h.normalize(data['language']))
    setAttr(source, 'location', h.normalize(data['location']))
    setAttr(source, 'LCCN', h.normalize(data['LCCN']))
    setAttr(source, 'mrnumber', h.normalize(data['mrnumber']))
    setAttr(source, 'price', h.normalize(data['price']))
    setAttr(source, 'size', h.normalize(data['size']))

    # Many-to-One Data
    if data['file'] != source.file:
        source.file = data['file']
        CHANGED = True

    if CHANGED:
        CHANGED = None      # It's crucial to reset the CHANGED global!
        source.datetimeModified = datetime.datetime.utcnow()
        return source
    return CHANGED