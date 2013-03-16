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
import datetime
import re
import os
from uuid import uuid4
import simplejson as json
from string import letters, digits
from random import sample
from pylons import request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from pylons.controllers.util import forward
from formencode.validators import Invalid
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql import asc
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import CorpusSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Corpus, CorpusBackup

log = logging.getLogger(__name__)

class CorporaController(BaseController):
    """Generate responses to requests on corpus resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """
    queryBuilder = SQLAQueryBuilder('Corpus', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all corpus resources.

        :URL: ``GET /corpora`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all corpus resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerloadCorpus(Session.query(Corpus))
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
        """Create a new corpus resource and return it.

        :URL: ``POST /corpora``
        :request body: JSON object representing the corpus to create.
        :returns: the newly created corpus.

        """
        try:
            schema = CorpusSchema()
            values = json.loads(unicode(request.body, request.charset))
            values['forms'] = [int(id) for id in h.formReferencePattern.findall(
                               values.get('content', u''))]
            state = h.getStateObject(values)
            data = schema.to_python(values, state)
            corpus = createNewCorpus(data)
            Session.add(corpus)
            Session.commit()
            createCorpusDir(corpus)
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
        
           See :func:`h.getDataForNewAction` to understand how the query
           string parameters can affect the contents of the lists in the
           returned dictionary.

        """
        return getDataForNewEdit(request.GET)

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
        corpus = h.eagerloadCorpus(Session.query(Corpus)).get(int(id))
        if corpus:
            try:
                schema = CorpusSchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                values['forms'] = h.getIdsOfFormsReferenced(values.get('content', u''))
                data = schema.to_python(values, state)
                corpusDict = corpus.getDict()
                corpus = updateCorpus(corpus, data)
                # corpus will be False if there are no changes (cf. updateCorpus).
                if corpus:
                    backupCorpus(corpusDict)
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
        corpus = h.eagerloadCorpus(Session.query(Corpus)).get(id)
        if corpus:
            corpusDict = corpus.getDict()
            backupCorpus(corpusDict)
            Session.delete(corpus)
            Session.commit()
            removeCorpusDirectory(corpus)
            return corpusDict
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
        corpus = h.eagerloadCorpus(Session.query(Corpus)).get(id)
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
        corpus = h.eagerloadCorpus(Session.query(Corpus)).get(id)
        if corpus:
            return {'data': getDataForNewEdit(request.GET),
                    'corpus': corpus}
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the corpus with ``corpus.id==id`` and its previous versions.

        :URL: ``GET /corpora/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            corpus whose history is requested.
        :returns: A dictionary of the form::

                {"corpus": { ... }, "previousVersions": [ ... ]}

            where the value of the ``corpus`` key is the corpus whose
            history is requested and the value of the ``previousVersions`` key
            is a list of dictionaries representing previous versions of the
            corpus.

        """
        corpus, previousVersions = h.getModelAndPreviousVersions('Corpus', id)
        if corpus or previousVersions:
            return {'corpus': corpus,
                    'previousVersions': previousVersions}
        else:
            response.status_int = 404
            return {'error': 'No corpora or corpus backups match %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def writetofile(self, id):
        """Write the forms constituting the corpus to a file in a format corresponding to the corpus type.

        :URL: ``PUT /corpora/writetofile/id``
        :param str id: the ``id`` value of the corpus.
        :returns: I don't know ... maybe it will serve the written file ...  Does
            this need to be done in a separate thread?

        NEEDS WORK ...
        
        IDEA: this could be a read/write action.  E.g., rename it to ``getasfile``
        and it could write the file if it doesn't yet exist, re-write it if it's
        out of date and return the file in any case ...  hmm, but maybe two
        separate actions are better since it may be desirable to write to file
        without retrieving a potentially large file ...

        """
        corpus = Session.query(Corpus).get(id)
        if corpus:
            corpusDirPath = getCorpusDirPath(corpus)
            # writeToFile(corpus, corpusDirPath)
            return 'the output of corpus.writetofile, whatever that is'
        else:
            response.status_int = 404
            return {'error': 'There is no corpus with id %s' % id}

    

################################################################################
# Backup corpus
################################################################################

def backupCorpus(corpusDict):
    """Backup a corpus.

    :param dict corpusDict: a representation of a corpus model.
    :returns: ``None``

    """
    corpusBackup = CorpusBackup()
    corpusBackup.vivify(corpusDict)
    Session.add(corpusBackup)


################################################################################
# Corpus Create & Update Functions
################################################################################

def createNewCorpus(data):
    """Create a new corpus.

    :param dict data: the data for the corpus to be created.
    :returns: an SQLAlchemy model object representing the corpus.

    .. note::
    
        I have opted not to complicate corpora by giving meaning to the
        "restricted" tag where they are concerned.  Given that a corpus' forms
        can be determined by a form search model and are therefore variable, it
        does not seem practical to toggle restricted status based on the status
        of any number of forms.  Since the corpus resource returns its list of
        forms only when its file is returned, this lack of restrictability
        should not be an issue.  When a file is written to disk, the system
        could determine restricted status for that file or even write a version
        of it for restricted users ...

    """
    corpus = Corpus()
    corpus.UUID = unicode(uuid4())
    corpus.name = h.normalize(data['name'])
    corpus.type = data['type']
    corpus.description = h.normalize(data['description'])
    corpus.content = h.normalize(data['content'])
    corpus.formSearch = data['formSearch']
    corpus.tags = data['tags']
    corpus.forms = data['forms']
    corpus.enterer = corpus.modifier = session['user']
    corpus.datetimeModified = corpus.datetimeEntered = h.now()
    return corpus


def updateCorpus(corpus, data):
    """Update a corpus.

    :param page: the corpus model to be updated.
    :param dict data: representation of the updated corpus.
    :returns: the updated corpus model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = h.setAttr(corpus, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(corpus, 'description', h.normalize(data['description']), changed)
    changed = h.setAttr(corpus, 'script', h.normalize(data['script']), changed)

    if changed:
        corpus.modifier = session['user']
        corpus.datetimeModified = h.now()
        return corpus
    return changed

def saveCorpusScript(corpus):
    """Save the corpus's ``script`` value to disk as ``corpus_<id>.script``.
    
    Also create the corpus compiler shell script, i.e., ``corpus_<id>.sh``
    which will be used to compile the corpus FST to a binary.

    :param corpus: a corpus model.
    :returns: the absolute path to the newly created corpus script file.

    """
    try:
        corpusDirPath = createCorpusDir(corpus)
        corpusScriptPath = getCorpusFilePath(corpus, 'script')
        corpusBinaryPath = getCorpusFilePath(corpus, 'binary')
        corpusCompilerPath = getCorpusFilePath(corpus, 'compiler')
        with codecs.open(corpusScriptPath, 'w', 'utf8') as f:
            f.write(corpus.script)
        # The compiler shell script loads the foma script and compiles it to binary form.
        with open(corpusCompilerPath, 'w') as f:
            f.write('#!/bin/sh\nfoma -e "source %s" -e "regex corpus;" -e "save stack %s" -e "quit"' % (
                    corpusScriptPath, corpusBinaryPath))
        os.chmod(corpusCompilerPath, 0744)
        return corpusScriptPath
    except Exception:
        return None

def createCorpusDir(corpus):
    """Create the directory to hold the corpus-as-file-object.
    
    :param corpus: a corpus model object.
    :returns: an absolute path to the directory for the corpus.

    """
    corpusDirPath = getCorpusDirPath(corpus)
    h.makeDirectorySafely(corpusDirPath)
    return corpusDirPath

def getCorpusDirPath(corpus):
    """Return the path to a corpus's directory.
    
    :param corpus: a corpus model object.
    :returns: an absolute path to the directory for the corpus.

    """
    return os.path.join(config['analysis_data'],
                                    'corpus', 'corpus_%d' % corpus.id)

def getCorpusFilePath(corpus, fileType='script'):
    """Return the path to a corpus's file of the given type.
    
    :param corpus: a corpus model object.
    :param str fileType: one of 'script', 'binary', 'compiler', or 'tester'.
    :returns: an absolute path to the corpus's script file.

    """
    extMap = {'script': 'script', 'binary': 'foma', 'compiler': 'sh', 'tester': 'tester.sh'}
    return os.path.join(getCorpusDirPath(corpus),
            'corpus_%d.%s' % (corpus.id, extMap.get(fileType, 'script')))

def removeCorpusDirectory(corpus):
    """Remove the directory of the corpus model and everything in it.
    
    :param corpus: a corpus model object.
    :returns: an absolute path to the directory for the corpus.

    """
    try:
        corpusDirPath = getCorpusDirPath(corpus)
        rmtree(corpusDirPath)
        return corpusDirPath
    except Exception:
        return None


def fomaOutputFile2Dict(file_):
    """Return the content of the foma output file ``file_`` as a dict.

    :param file file_: utf8-encoded file object with tab-delimited i/o pairs.
    :returns: dictionary of the form ``{i1: [01, 02, ...], i2: [...], ...}``.

    """
    result = {}
    for line in file_:
        line = line.strip()
        if line:
            i, o = line.split('\t')[:2]
            try:
                result[i].append(o)
            except (KeyError, ValueError):
                result[i] = [o]
    return result

def phonologize(inputs, corpus, corpusBinaryPath, user):
    """Phonologize the inputs using the corpus's compiled script.
    
    :param list inputs: a list of morpho-phonemic transcriptions.
    :param corpus: a corpus model.
    :param str corpusBinaryPath: an absolute path to a compiled corpus script.
    :param user: a user model.
    :returns: a dictionary: ``{input1: [o1, o2, ...], input2: [...], ...}``

    """
    randomString = h.generateSalt()
    corpusDirPath = getCorpusDirPath(corpus)
    inputsFilePath = os.path.join(corpusDirPath,
            'inputs_%s_%s.txt' % (user.username, randomString))
    outputsFilePath = os.path.join(corpusDirPath,
            'outputs_%s_%s.txt' % (user.username, randomString))
    applydownFilePath = os.path.join(corpusDirPath,
            'applydown_%s_%s.sh' % (user.username, randomString))
    with codecs.open(inputsFilePath, 'w', 'utf8') as f:
        f.write(u'\n'.join(inputs))
    with codecs.open(applydownFilePath, 'w', 'utf8') as f:
        f.write('#!/bin/sh\ncat %s | flookup -i %s' % (
                inputsFilePath, corpusBinaryPath))
    os.chmod(applydownFilePath, 0744)
    with open(os.devnull, 'w') as devnull:
        with codecs.open(outputsFilePath, 'w', 'utf8') as outfile:
            p = Popen(applydownFilePath, shell=False, stdout=outfile, stderr=devnull)
    p.communicate()
    with codecs.open(outputsFilePath, 'r', 'utf8') as f:
        result = fomaOutputFile2Dict(f)
    os.remove(inputsFilePath)
    os.remove(outputsFilePath)
    os.remove(applydownFilePath)
    return result


def getTests(corpus):
    """Return any tests defined in a corpus's script as a dictionary."""
    result = {}
    testLines = [l[6:] for l in corpus.script.splitlines() if l[:6] == u'#test ']
    for l in testLines:
        try:
            i, o = map(unicode.strip, l.split(u'->'))
            try:
                result[i].append(o)
            except KeyError:
                result[i] = [o]
        except ValueError:
            pass
    return result


def runTests(corpus, corpusBinaryPath, user):
    """Run the test defined in the corpus's script and return a report.
    
    :param corpus: a corpus model.
    :param str corpusBinaryPath: an absolute path to the corpus's compiled foma script.
    :param user: a user model.
    :returns: a dictionary representing the report on the tests.

    A line in a corpus's script that begins with "#test " signifies a
    test.  After "#test " there should be a string of characters followed by
    "->" followed by another string of characters.  The first string is the
    underlying representation and the second is the anticipated surface
    representation.  Requests to ``GET /corpora/runtests/id`` will cause
    the OLD to run a corpus script against its tests and return a
    dictionary detailing the expected and actual outputs of each input in the
    transcription.  :func:`runTests` generates that dictionary.

    """

    tests = getTests(corpus)
    if not tests:
        response.status_int = 400
        return {'error': 'The script of corpus %d contains no tests.' % corpus.id}
    results = phonologize(tests.keys(), corpus, corpusBinaryPath, user)
    return dict([(t, {'expected': tests[t], 'actual': results[t]}) for t in tests])


def getDataForNewEdit(GET_params):
    """Return the data needed to create a new corpus or edit one."""
    mandatoryAttributes = ['corpusTypes']
    modelNameMap = {
        'formSearches': 'FormSearch',
        'users': 'User',
        'tags': 'Tag'
    }
    getterMap = {
        'formSearches': h.getMiniDictsGetter('FormSearch'),
        'users': h.getMiniDictsGetter('User'),
        'tags': h.getMiniDictsGetter('Tag'),
        'corpusTypes': h.corpusTypes
    }
    return getDataForNewAction(GET_params, getterMap, modelNameMap, mandatoryAttributes)
