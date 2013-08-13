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

"""Contains the :class:`SourcesController` and its auxiliary functions.

.. module:: sources
   :synopsis: Contains the sources controller and its auxiliary functions.

"""

import logging
import datetime
import simplejson as json
from pylons import request, response, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import SourceSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Source
from onlinelinguisticdatabase.lib.bibtex import entry_types

log = logging.getLogger(__name__)

class SourcesController(BaseController):
    """Generate responses to requests on source resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('Source', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self):
        """Return the list of source resources matching the input JSON query.

        :URL: ``SEARCH /sources`` (or ``POST /sources/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        """
        try:
            json_search_params = unicode(request.body, request.charset)
            python_search_params = json.loads(json_search_params)
            query = self.query_builder.get_SQLA_query(python_search_params.get('query'))
            return h.add_pagination(query, python_search_params.get('paginator'))
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except (OLDSearchParseError, Invalid), e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except:
            response.status_int = 400
            return {'error': u'The specified search parameters generated an invalid database query'}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """Return the data necessary to search the source resources.

        :URL: ``GET /sources/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all source resources.

        :URL: ``GET /sources`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all source resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = Session.query(Source)
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
        """Create a new source resource and return it.

        :URL: ``POST /sources``
        :request body: JSON object representing the source to create.
        :returns: the newly created source.

        """
        try:
            schema = SourceSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.get_state_object(values)
            data = schema.to_python(values, state)
            source = create_new_source(data)
            Session.add(source)
            Session.commit()
            return source
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
        """Return the data necessary to create a new source.

        :URL: ``GET /sources/new``.
        :returns: a dictionary containing the valid BibTeX entry types.

        """
        return {'types': sorted(entry_types.keys())}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a source and return it.
        
        :URL: ``PUT /sources/id``
        :Request body: JSON object representing the source with updated attribute values.
        :param str id: the ``id`` value of the source to be updated.
        :returns: the updated source model.

        """
        source = Session.query(Source).get(int(id))
        if source:
            try:
                schema = SourceSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                source = update_source(source, data)
                # source will be False if there are no changes (cf. update_source).
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

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing source and return it.

        :URL: ``DELETE /sources/id``
        :param str id: the ``id`` value of the source to be deleted.
        :returns: the deleted source model.

        """
        source = Session.query(Source).get(id)
        if source:
            Session.delete(source)
            Session.commit()
            return source
        else:
            response.status_int = 404
            return {'error': 'There is no source with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a source.
        
        :URL: ``GET /sources/id``
        :param str id: the ``id`` value of the source to be returned.
        :returns: a source model object.

        .. note::

            A source associated to a restricted file will still return a subset
            of the restricted file's metadata.  However, restricted users will
            be unable to retrieve the file data of the file because of the
            authorization logic in the retrieve action of the files controller.

        """
        source = Session.query(Source).get(id)
        if source:
            return source
        else:
            response.status_int = 404
            return {'error': 'There is no source with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a source and the data needed to update it.

        :URL: ``GET /sources/edit``
        :param str id: the ``id`` value of the source that will be updated.
        :returns: a dictionary of the form::

                {"source": {...}, "data": {...}}

            where the value of the ``source`` key is a dictionary
            representation of the source and the value of the ``data`` key
            is the list of BibTeX entry types.

        """
        source = Session.query(Source).get(id)
        if source:
            return {'data': {'types': sorted(entry_types.keys())}, 'source': source}
        else:
            response.status_int = 404
            return {'error': 'There is no source with id %s' % id}


################################################################################
# Source Create & Update Functions
################################################################################

def create_new_source(data):
    """Create a new source.

    :param dict data: the data for the source to be created.
    :returns: an SQLAlchemy model object representing the source.

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
    source.key_field = h.normalize(data['key_field'])
    source.month = h.normalize(data['month'])
    source.note = h.normalize(data['note'])
    source.number = h.normalize(data['number'])
    source.organization = h.normalize(data['organization'])
    source.pages = h.normalize(data['pages'])
    source.publisher = h.normalize(data['publisher'])
    source.school = h.normalize(data['school'])
    source.series = h.normalize(data['series'])
    source.title = h.normalize(data['title'])
    source.type_field = h.normalize(data['type_field'])
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

    # Many-to-one: file, crossref_source
    source.file = data['file']
    source.crossref_source = data['crossref_source']

    # OLD-generated Data
    source.datetime_modified = datetime.datetime.utcnow()

    return source


def update_source(source, data):
    """Update a source.

    :param source: the source model to be updated.
    :param dict data: representation of the updated source.
    :returns: the updated source model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False

    # Unicode Data
    changed = source.set_attr('type', h.normalize(data['type']), changed)
    changed = source.set_attr('key', h.normalize(data['key']), changed)
    changed = source.set_attr('address', h.normalize(data['address']), changed)
    changed = source.set_attr('annote', h.normalize(data['annote']), changed)
    changed = source.set_attr('author', h.normalize(data['author']), changed)
    changed = source.set_attr('booktitle', h.normalize(data['booktitle']), changed)
    changed = source.set_attr('chapter', h.normalize(data['chapter']), changed)
    changed = source.set_attr('crossref', h.normalize(data['crossref']), changed)
    changed = source.set_attr('edition', h.normalize(data['edition']), changed)
    changed = source.set_attr('editor', h.normalize(data['editor']), changed)
    changed = source.set_attr('howpublished', h.normalize(data['howpublished']), changed)
    changed = source.set_attr('institution', h.normalize(data['institution']), changed)
    changed = source.set_attr('journal', h.normalize(data['journal']), changed)
    changed = source.set_attr('key_field', h.normalize(data['key_field']), changed)
    changed = source.set_attr('month', h.normalize(data['month']), changed)
    changed = source.set_attr('note', h.normalize(data['note']), changed)
    changed = source.set_attr('number', h.normalize(data['number']), changed)
    changed = source.set_attr('organization', h.normalize(data['organization']), changed)
    changed = source.set_attr('pages', h.normalize(data['pages']), changed)
    changed = source.set_attr('publisher', h.normalize(data['publisher']), changed)
    changed = source.set_attr('school', h.normalize(data['school']), changed)
    changed = source.set_attr('series', h.normalize(data['series']), changed)
    changed = source.set_attr('title', h.normalize(data['title']), changed)
    changed = source.set_attr('type_field', h.normalize(data['type_field']), changed)
    changed = source.set_attr('url', data['url'], changed)
    changed = source.set_attr('volume', h.normalize(data['volume']), changed)
    changed = source.set_attr('year', data['year'], changed)
    changed = source.set_attr('affiliation', h.normalize(data['affiliation']), changed)
    changed = source.set_attr('abstract', h.normalize(data['abstract']), changed)
    changed = source.set_attr('contents', h.normalize(data['contents']), changed)
    changed = source.set_attr('copyright', h.normalize(data['copyright']), changed)
    changed = source.set_attr('ISBN', h.normalize(data['ISBN']), changed)
    changed = source.set_attr('ISSN', h.normalize(data['ISSN']), changed)
    changed = source.set_attr('keywords', h.normalize(data['keywords']), changed)
    changed = source.set_attr('language', h.normalize(data['language']), changed)
    changed = source.set_attr('location', h.normalize(data['location']), changed)
    changed = source.set_attr('LCCN', h.normalize(data['LCCN']), changed)
    changed = source.set_attr('mrnumber', h.normalize(data['mrnumber']), changed)
    changed = source.set_attr('price', h.normalize(data['price']), changed)
    changed = source.set_attr('size', h.normalize(data['size']), changed)

    # Many-to-One Data
    changed = source.set_attr('file', data['file'], changed)
    changed = source.set_attr('crossref_source', data['crossref_source'], changed)

    if changed:
        source.datetime_modified = datetime.datetime.utcnow()
        return source
    return changed
