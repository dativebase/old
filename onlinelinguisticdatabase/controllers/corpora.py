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

"""Contains the :class:`CorporaController` and its auxiliary functions.

.. module:: corpora
   :synopsis: Contains the corpora controller and its auxiliary functions.

"""

import logging
import os
import codecs
from uuid import uuid4
from shutil import rmtree
import simplejson as json
from paste.fileapp import FileApp
from pylons import request, response, session, config
from pylons.controllers.util import forward
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import CorpusSchema, CorpusFormatSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Corpus, CorpusBackup, CorpusFile, Form
from subprocess import call, Popen

log = logging.getLogger(__name__)

class CorporaController(BaseController):
    """Generate responses to requests on corpus resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """
    query_builder_for_ordering = SQLAQueryBuilder('Corpus', config=config)
    query_builder = SQLAQueryBuilder('Form', config=config)

    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search_corpora(self):
        """Return the list of corpora that match the input JSON query.

        :URL: ``SEARCH/POST /corpora/searchcorpora``
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        .. note::

            This action *does* result in a search across corpora resources.
            Contrast this with the `search` method below which allows one to
            search across the forms in a specified corpus.

        """

        try:
            json_search_params = unicode(request.body, request.charset)
            python_search_params = json.loads(json_search_params)
            SQLAQuery = self.query_builder_for_ordering.get_SQLA_query(
                python_search_params.get('query'))
            return h.add_pagination(SQLAQuery,
                python_search_params.get('paginator'))
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
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def search(self, id):
        """Return the forms from corpus ``id`` that match the input JSON query.

        :param str id: the id value of the corpus to be searched.
        :URL: ``SEARCH /corpora/id` (or ``POST /corpora/id/search``)
        :request body: A JSON object of the form::

                {"query": {"filter": [ ... ], "order_by": [ ... ]},
                 "paginator": { ... }}

            where the ``order_by`` and ``paginator`` attributes are optional.

        .. note::

            The corpora search action is different from typical search actions
            in that it does not return an array of corpora but of forms that
            are in the corpus whose ``id`` value matches ``id``.  This action
            resembles the search action of the ``RememberedformsController``.

        """
        corpus = Session.query(Corpus).get(id)
        if corpus:
            try:
                json_search_params = unicode(request.body, request.charset)
                python_search_params = json.loads(json_search_params)
                query = h.eagerload_form(
                    self.query_builder.get_SQLA_query(python_search_params.get('query')))
                query = query.filter(Form.corpora.contains(corpus))
                query = h.filter_restricted_models('Form', query)
                return h.add_pagination(query, python_search_params.get('paginator'))
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except (OLDSearchParseError, Invalid), e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
            except Exception, e:
                log.warn("%s's filter expression (%s) raised an unexpected exception: %s." % (
                    h.get_user_full_name(session['user']), request.body, e))
                response.status_int = 400
                return {'error': u'The specified search parameters generated an invalid database query'}
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search(self):
        """Return the data necessary to search the form resources.

        :URL: ``GET /corpora/new_search``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        """
        return {'search_parameters': h.get_search_parameters(self.query_builder)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def new_search_corpora(self):
        """Return the data necessary to search across corpus resources.

        :URL: ``GET /corpora/new_search_corpora``
        :returns: ``{"search_parameters": {"attributes": { ... }, "relations": { ... }}``

        .. note::

            Contrast this action with `new_search`, which returns the data
            needed to search across the forms of a corpus.

        """
        return {'search_parameters':
            h.get_search_parameters(self.query_builder_for_ordering)}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all corpus resources.

        :URL: ``GET /corpora`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all corpus resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_corpus(Session.query(Corpus))
            query = h.add_order_by(query, dict(request.GET), self.query_builder_for_ordering)
            return h.add_pagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """Create a new corpus resource and return it.

        :URL: ``POST /corpora``
        :request body: JSON object representing the corpus to create.
        :returns: the newly created corpus.

        """
        try:
            schema = CorpusSchema()
            values = json.loads(unicode(request.body, request.charset))
            state = h.get_state_object(values)
            state.config = config
            data = schema.to_python(values, state)
            corpus = create_new_corpus(data)
            Session.add(corpus)
            Session.commit()
            create_corpus_dir(corpus)
            return corpus
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
        """Return the data necessary to create a new corpus.

        :URL: ``GET /corpora/new``.
        :returns: a dictionary of resources.

        .. note::
        
           See :func:`h.get_data_for_new_action` to understand how the query
           string parameters can affect the contents of the lists in the
           returned dictionary.

        """
        return get_data_for_new_edit(dict(request.GET))

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a corpus and return it.
        
        :URL: ``PUT /corpora/id``
        :Request body: JSON object representing the corpus with updated attribute values.
        :param str id: the ``id`` value of the corpus to be updated.
        :returns: the updated corpus model.

        """
        corpus = h.eagerload_corpus(Session.query(Corpus)).get(int(id))
        if corpus:
            try:
                schema = CorpusSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                state.config = config
                data = schema.to_python(values, state)
                corpus_dict = corpus.get_dict()
                corpus = update_corpus(corpus, data)
                # corpus will be False if there are no changes (cf. update_corpus).
                if corpus:
                    backup_corpus(corpus_dict)
                    Session.add(corpus)
                    Session.commit()
                    return corpus
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
            return {'error': 'There is no corpus with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing corpus and return it.

        :URL: ``DELETE /corpora/id``
        :param str id: the ``id`` value of the corpus to be deleted.
        :returns: the deleted corpus model.

        """
        corpus = h.eagerload_corpus(Session.query(Corpus)).get(id)
        if corpus:
            corpus_dict = corpus.get_dict()
            backup_corpus(corpus_dict)
            Session.delete(corpus)
            Session.commit()
            remove_corpus_directory(corpus)
            return corpus_dict
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a corpus.

        :URL: ``GET /corpora/id``
        :param str id: the ``id`` value of the corpus to be returned.
        :returns: a corpus model object.

        """
        corpus = h.eagerload_corpus(Session.query(Corpus)).get(id)
        if corpus:
            return corpus
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a corpus and the data needed to update it.

        :URL: ``GET /corpora/edit``
        :param str id: the ``id`` value of the corpus that will be updated.
        :returns: a dictionary of the form::

                {"corpus": {...}, "data": {...}}

            where the value of the ``corpus`` key is a dictionary
            representation of the corpus and the value of the ``data`` key
            is an empty dictionary.

        """
        corpus = h.eagerload_corpus(Session.query(Corpus)).get(id)
        if corpus:
            return {'data': get_data_for_new_edit(request.GET),
                    'corpus': corpus}
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the corpus with ``corpus.id==id`` and its previous versions.

        :URL: ``GET /corpora/id/history``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            corpus whose history is requested.
        :returns: A dictionary of the form::

                {"corpus": { ... }, "previous_versions": [ ... ]}

            where the value of the ``corpus`` key is the corpus whose
            history is requested and the value of the ``previous_versions`` key
            is a list of dictionaries representing previous versions of the
            corpus.

        """
        corpus, previous_versions = h.get_model_and_previous_versions('Corpus', id)
        if corpus or previous_versions:
            return {'corpus': corpus,
                    'previous_versions': previous_versions}
        else:
            response.status_int = 404
            return {'error': 'No corpora or corpus backups match %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def writetofile(self, id):
        """Write the corpus to a file in the format specified in the request body.

        :URL: ``PUT /corpora/id/writetofile``
        :Request body: JSON object of the form ``{"format": "..."}.``
        :param str id: the ``id`` value of the corpus.
        :returns: the modified corpus model (or a JSON error message).

        """
        #corpus = h.eagerload_corpus(Session.query(Corpus), eagerload_forms=True).get(id)
        corpus = Session.query(Corpus).get(id)
        if corpus:
            try:
                schema = CorpusFormatSchema
                values = json.loads(unicode(request.body, request.charset))
                format_ = schema.to_python(values)['format']
                return write_to_file(corpus, format_)
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    @h.restrict('GET')
    @h.authenticate_with_JSON
    def servefile(self, id, file_id):
        """Return the corpus as a file in the format specified in the URL query string.

        :URL: ``PUT /corpora/id/servefile/file_id``.
        :param str id: the ``id`` value of the corpus.
        :param str file_id: the ``id`` value of the corpus file.
        :returns: the file data

        """
        corpus = Session.query(Corpus).get(id)
        if corpus:
            try:
                corpus_file = filter(lambda cf: cf.id == int(file_id), corpus.files)[0]
                corpus_file_path = os.path.join(get_corpus_dir_path(corpus),
                                              '%s.gz' % corpus_file.filename)
                if authorized_to_access_corpus_file(session['user'], corpus_file):
                    return forward(FileApp(corpus_file_path, content_type='application/x-gzip'))
                else:
                    response.status_int = 403
                    return json.dumps(h.unauthorized_msg)
            except Exception:
                response.status_int = 400
                return json.dumps({'error': 'Unable to serve corpus file %d of corpus %d' % (
                        file_id, id)})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no corpus with id %s' % id})


    @h.jsonify
    @h.restrict('SEARCH', 'POST')
    @h.authenticate
    def tgrep2(self, id):
        """Search the corpus-as-treebank using Tgrep2.

        :URL: ``SEARCH/POST /corpora/id/tgrep2``.
        :Request body: JSON object with obligatory 'tgrep2pattern' attribute and
            optional 'paginator' and 'order_by' attributes.
        :param str id: the ``id`` value of the corpus.
        :returns: an array of forms as JSON objects

        """
        if not h.command_line_program_installed('tgrep2'):
            response.status_int = 400
            return {'error': 'TGrep2 is not installed.'}
        corpus = Session.query(Corpus).get(id)
        if corpus:
            try:
                treebank_corpus_file_object = filter(lambda cf: cf.format == u'treebank',
                        corpus.files)[0]
                corpus_dir_path = get_corpus_dir_path(corpus)
                tgrep2_corpus_file_path = os.path.join(corpus_dir_path,
                        '%s.t2c' % treebank_corpus_file_object.filename)
            except Exception:
                response.status_int = 400
                return {'error': 'Corpus %d has not been written to file as a treebank.'}
            if not os.path.exists(tgrep2_corpus_file_path):
                response.status_int = 400
                return {'error': 'Corpus %d has not been written to file as a treebank.'}
            #if not authorized_to_access_corpus_file(session['user'], treebank_corpus_file_object):
            #    response.status_int = 403
            #    return h.unauthorized_msg
            try:
                request_params = json.loads(unicode(request.body, request.charset))
                try:
                    tgrep2pattern = request_params['tgrep2pattern']
                    assert isinstance(tgrep2pattern, basestring)
                except Exception:
                    response.status_int = 400
                    return {'errors': {'tgrep2pattern':
                        'A tgrep2pattern attribute must be supplied and must have a unicode/string value'}}
                tmp_path = os.path.join(corpus_dir_path, '%s%s.txt' % (session['user'].username, h.generate_salt()))
                with open(os.devnull, "w") as fnull:
                    with open(tmp_path, 'w') as stdout:
                        # The -wu option causes TGrep2 to print only the root symbol of each matching tree
                        process = Popen(['tgrep2', '-c', tgrep2_corpus_file_path, '-wu', tgrep2pattern],
                            stdout=stdout, stderr=fnull)
                        process.communicate()
                match_ids = filter(None, map(get_form_ids_from_tgrep2_output_line, open(tmp_path, 'r')))
                os.remove(tmp_path)
                if match_ids:
                    query = h.eagerload_form(Session.query(Form)).filter(Form.id.in_(match_ids))
                    query = h.filter_restricted_models('Form', query)
                    query = h.add_order_by(query, request_params.get('order_by'), self.query_builder)
                    result = h.add_pagination(query, request_params.get('paginator'))
                elif request_params.get('paginator'):
                    paginator = request_params['paginator']
                    paginator['count'] = 0
                    result = {'paginator': paginator, 'items': []}
                else:
                    result = []
                return result
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
            except Exception, e:
                response.status_int = 400
                return {'error': 'Unable to perform TGrep2 search: %s.' % e}
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def get_word_category_sequences(self, id):
        """Return the category sequence types of validly morphologically analyzed words
        in the corpus with ``id``, including the id exemplars of said types.
        """
        corpus = Session.query(Corpus).get(id)
        if corpus:
            word_category_sequences = h.get_word_category_sequences(corpus)
            minimum_token_count = int(request.GET.get('minimum_token_count', 0))
            if minimum_token_count:
                word_category_sequences = [(''.join(sequence), ids) for sequence, ids in word_category_sequences
                        if len(ids) >= minimum_token_count]
            return word_category_sequences
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

def get_form_ids_from_tgrep2_output_line(line):
    try:
        return int(line.split('-')[1])
    except Exception:
        return None

def authorized_to_access_corpus_file(user, corpus_file):
    """Return True if user is authorized to access the corpus file."""
    if corpus_file.restricted and user.role != u'administrator' and \
    user not in h.get_unrestricted_users():
        return False
    return True

def write_to_file(corpus, format_):
    """Write the corpus to file in the specified format.

    Write the corpus to a binary file, create or update a corpus file model and
    associate it to the corpus model (if necessary).

    :param corpus: a corpus model.
    :param str format_: the format of the file to be written.
    :returns: the corpus modified appropriately (assuming success)
    :side effects: may write (a) file(s) to disk and update/create a corpus file model.

    .. note::

        It may be desirable/necessary to perform the corpus file writing
        asynchronously using a dedicated corpus-file-worker.

    """

    error_msg = lambda msg: {'error': u'Unable to write corpus %d to file with format "%s". (%s)' % (
                corpus.id, format_, msg)}

    def update_corpus_file(corpus, filename, modifier, datetime_modified, restricted):
        """Update the corpus file model of ``corpus`` that matches ``filename``."""
        corpus_file = [cf for cf in corpus.files if cf.filename == filename][0]
        corpus_file.restricted = restricted
        corpus_file.modifier = modifier
        corpus_file.datetime_modified = corpus.datetime_modified = now

    def generate_new_corpus_file(corpus, filename, format_, creator, datetime_created, restricted):
        """Create a corpus file model with ``filename`` and append it to ``corpus.files``."""
        corpus_file = CorpusFile()
        corpus_file.restricted = restricted
        corpus.files.append(corpus_file)
        corpus_file.filename = filename
        corpus_file.format = format_
        corpus_file.creator = corpus_file.modifier = creator
        corpus_file.datetime_created = corpus_file.datetime_modified = datetime_created
        corpus.datetime_modified = datetime_created

    def destroy_file(file_path):
        try:
            rmtree(file_path)
        except Exception:
            pass

    corpus_file_path = get_corpus_file_path(corpus, format_)
    update = os.path.exists(corpus_file_path) # If True, we are upating
    restricted = False

    # Create the corpus file on the filesystem
    try:
        writer = h.corpus_formats[format_]['writer']
        if corpus.form_search:   # ``form_search`` value negates any content.
            with codecs.open(corpus_file_path, 'w', 'utf8') as f:
                for form in corpus.forms:
                    if not restricted and "restricted" in [t.name for t in form.tags]:
                        restricted = True
                    f.write(writer(form))
        else:
            form_references = corpus.get_form_references(corpus.content)
            forms = dict([(f.id, f) for f in corpus.forms])
            with codecs.open(corpus_file_path, 'w', 'utf8') as f:
                for id in form_references:
                    form = forms[id]
                    if not restricted and "restricted" in [t.name for t in form.tags]:
                        restricted = True
                    f.write(writer(form))
        gzipped_corpus_file_path = h.compress_file(corpus_file_path)
        create_tgrep2_corpus_file(gzipped_corpus_file_path, format_)
    except Exception, e:
        destroy_file(corpus_file_path)
        response.status_int = 400
        return error_msg(e)

    # Update/create the corpus_file object
    try:
        now = h.now()
        session['user'] = Session.merge(session['user'])
        user = session['user']
        corpus_filename = os.path.split(corpus_file_path)[1]
        if update:
            try:
                update_corpus_file(corpus, corpus_filename, user, now, restricted)
            except Exception:
                generate_new_corpus_file(corpus, corpus_filename, format_, user,
                                      now, restricted)
        else:
            generate_new_corpus_file(corpus, corpus_filename, format_, user, now,
                                  restricted)
    except Exception, e:
        destroy_file(corpus_file_path)
        response.status_int = 400
        return error_msg(e)
    Session.commit()
    return corpus

def create_tgrep2_corpus_file(gzipped_corpus_file_path, format_):
    """Use TGrep2 to create a .t2c corpus file from the gzipped file of phrase-structure trees.

    :param str gzipped_corpus_file_path: absolute path to the gzipped corpus file.
    :param str format_: the format in which the corpus has just been written to disk.
    :returns: the absolute path to the .t2c file or ``False``.

    """
    if format_ == u'treebank' and h.command_line_program_installed('tgrep2'):

        out_path = '%s.t2c' % os.path.splitext(gzipped_corpus_file_path)[0]
        with open(os.devnull, "w") as fnull:
            call(['tgrep2', '-p', gzipped_corpus_file_path, out_path], stdout=fnull, stderr=fnull)
        if os.path.exists(out_path):
            return out_path
        return False
    return False

################################################################################
# Backup corpus
################################################################################

def backup_corpus(corpus_dict):
    """Backup a corpus.

    :param dict corpus_dict: a representation of a corpus model.
    :returns: ``None``

    """
    corpus_backup = CorpusBackup()
    corpus_backup.vivify(corpus_dict)
    Session.add(corpus_backup)


################################################################################
# Corpus Create & Update Functions
################################################################################

def create_new_corpus(data):
    """Create a new corpus.

    :param dict data: the data for the corpus to be created.
    :returns: an SQLAlchemy model object representing the corpus.

    .. note::
    
        I have opted not to complicate corpora by giving meaning to the
        "restricted" tag where they are concerned.  Given that a corpus' forms
        can be determined by a form search model and are therefore variable, it
        does not seem practical to toggle restricted status based on the status
        of any number of forms.  The corpus files that may be associated to a
        corpus by requesting ``PUT /corpora/id/writetofile`` may, however, be
        restricted if a restricted form is written to file.

    """
    corpus = Corpus()
    corpus.UUID = unicode(uuid4())
    corpus.name = h.normalize(data['name'])
    corpus.description = h.normalize(data['description'])
    corpus.content = data['content']
    corpus.form_search = data['form_search']
    corpus.forms = data['forms']
    corpus.tags = data['tags']
    corpus.enterer = corpus.modifier = session['user']
    corpus.datetime_modified = corpus.datetime_entered = h.now()
    return corpus

def update_corpus(corpus, data):
    """Update a corpus.

    :param corpus: the corpus model to be updated.
    :param dict data: representation of the updated corpus.
    :returns: the updated corpus model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = corpus.set_attr('name', h.normalize(data['name']), changed)
    changed = corpus.set_attr('description', h.normalize(data['description']), changed)
    changed = corpus.set_attr('content', data['content'], changed)
    changed = corpus.set_attr('form_search', data['form_search'], changed)

    tags_to_add = [t for t in data['tags'] if t]
    forms_to_add = [f for f in data['forms'] if f]
    if set(tags_to_add) != set(corpus.tags):
        corpus.tags = tags_to_add
        changed = True
    if set(forms_to_add) != set(corpus.forms):
        corpus.forms = forms_to_add
        changed = True

    if changed:
        session['user'] = Session.merge(session['user'])
        corpus.modifier = session['user']
        corpus.datetime_modified = h.now()
        return corpus
    return changed

def create_corpus_dir(corpus):
    """Create the directory to hold the various forms of the corpus written to disk.
    
    :param corpus: a corpus model object.
    :returns: an absolute path to the directory for the corpus.

    """
    corpus_dir_path = get_corpus_dir_path(corpus)
    h.make_directory_safely(corpus_dir_path)
    return corpus_dir_path

def get_corpus_file_path(corpus, format_):
    """Return the path to a corpus's file of the given format.
    
    :param corpus: a corpus model object.
    :param str format_: the format for writing the corpus file.
    :returns: an absolute path to the corpus's file.

    .. note::
    
        It will be necessary to figure out other formats.

    """
    ext = h.corpus_formats[format_]['extension']
    sfx = h.corpus_formats[format_]['suffix']
    return os.path.join(get_corpus_dir_path(corpus),
            'corpus_%d%s.%s' % (corpus.id, sfx, ext))

def get_corpus_dir_path(corpus):
    return os.path.join(h.get_OLD_directory_path('corpora', config=config),
                        'corpus_%d' % corpus.id)

def remove_corpus_directory(corpus):
    """Remove the directory of the corpus model and everything in it.
    
    :param corpus: a corpus model object.
    :returns: an absolute path to the directory for the corpus.

    """
    try:
        corpus_dir_path = get_corpus_dir_path(corpus)
        rmtree(corpus_dir_path)
        return corpus_dir_path
    except Exception:
        return None


def get_data_for_new_edit(GET_params):
    """Return the data needed to create a new corpus or edit one."""
    mandatory_attributes = ['corpus_formats']
    model_name_map = {
        'form_searches': 'FormSearch',
        'users': 'User',
        'tags': 'Tag'
    }
    getter_map = {
        'form_searches': h.get_mini_dicts_getter('FormSearch'),
        'users': h.get_mini_dicts_getter('User'),
        'tags': h.get_mini_dicts_getter('Tag'),
        'corpus_formats': lambda: h.corpus_formats.keys()
    }
    return h.get_data_for_new_action(GET_params, getter_map, model_name_map, mandatory_attributes)


