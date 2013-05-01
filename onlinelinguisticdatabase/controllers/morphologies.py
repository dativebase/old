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

"""Contains the :class:`MorphologiesController` and its auxiliary functions.

.. module:: morphologies
   :synopsis: Contains the morphologies controller and its auxiliary functions.

"""

import logging
import simplejson as json
import os
import re
from uuid import uuid4
import codecs
from subprocess import Popen
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from shutil import rmtree
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import MorphologySchema, MorphemeSequencesSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Morphology, MorphologyBackup
from onlinelinguisticdatabase.lib.worker import worker_q

log = logging.getLogger(__name__)

class MorphologiesController(BaseController):
    """Generate responses to requests on morphology resources.

    A morphology, as here conceived, is an FST that is both a recognizer and a transducer, i.e.,
    it recognizes only those sequences of morphemes that are form valid words and it maps sequences
    of morphemes (in the general sense) to sequences of morpheme *forms*.  By a morpheme in the general
    sense, I mean to refer to ordered pairs of morpheme form and morpheme gloss.  That is, an OLD 
    morphology is an FST that maps something like 'chien|dog-s|PL' to 'chien-s' (and vice versa) and 
    which does not recognize 's|PL-chien|dog'.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    TODO: consider generating values for ``lexiconScript`` and ``rulesScript`` attributes
    which, by default, are concatenated to produce a value for the ``script`` attribute but 
    where such default auto-generation can be overridden by the user so that, for example, the
    auto-generated subscripts could be used to hand-write a more intelligent morphology FST script.

    """

    queryBuilder = SQLAQueryBuilder('Morphology', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all morphology resources.

        :URL: ``GET /morphologies`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all morphology resources.

        .. note::

           See :func:`utils.addOrderBy` and :func:`utils.addPagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerloadMorphology(Session.query(Morphology))
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
        """Create a new morphology resource and return it.

        :URL: ``POST /morphologies``
        :request body: JSON object representing the morphology to create.
        :returns: the newly created morphology.

        """
        try:
            schema = MorphologySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            morphology = createNewMorphology(data)
            Session.add(morphology)
            Session.commit()
            saveMorphologyScript(morphology)
            return morphology
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
        except MorphologyScriptGenerationError, e:
            response.status_int = 400
            return {'error': e}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """Return the data necessary to create a new morphology.

        :URL: ``GET /morphologies/new``.
        :returns: a dictionary containing summarizing the corpora.

        """
        return getDataForNewEdit(dict(request.GET))

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a morphology and return it.

        :URL: ``PUT /morphologies/id``
        :Request body: JSON object representing the morphology with updated attribute values.
        :param str id: the ``id`` value of the morphology to be updated.
        :returns: the updated morphology model.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(int(id))
        if morphology:
            try:
                schema = MorphologySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.getStateObject(values)
                state.id = id
                data = schema.to_python(values, state)
                morphologyDict = morphology.getDict()
                morphology = updateMorphology(morphology, data)
                # morphology will be False if there are no changes (cf. updateMorphology).
                if morphology:
                    backupMorphology(morphologyDict)
                    Session.add(morphology)
                    Session.commit()
                    saveMorphologyScript(morphology)
                    return morphology
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
            except MorphologyScriptGenerationError, e:
                response.status_int = 400
                return {'error': e}
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing morphology and return it.

        :URL: ``DELETE /morphologies/id``
        :param str id: the ``id`` value of the morphology to be deleted.
        :returns: the deleted morphology model.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(id)
        if morphology:
            morphologyDict = morphology.getDict()
            backupMorphology(morphologyDict)
            Session.delete(morphology)
            Session.commit()
            removeMorphologyDirectory(morphology)
            return morphology
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a morphology.

        :URL: ``GET /morphologies/id``
        :param str id: the ``id`` value of the morphology to be returned.
        :returns: a morphology model object.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(id)
        if morphology:
            return morphology
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a morphology and the data needed to update it.

        :URL: ``GET /morphologies/id/edit``
        :param str id: the ``id`` value of the morphology that will be updated.
        :returns: a dictionary of the form::

                {"morphology": {...}, "data": {...}}

            where the value of the ``morphology`` key is a dictionary
            representation of the morphology and the value of the ``data`` key
            is an empty dictionary.

        """
        morphology = h.eagerloadMorphology(Session.query(Morphology)).get(id)
        if morphology:
            return {'data': getDataForNewEdit(dict(request.GET)), 'morphology': morphology}
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the morphology with ``morphology.id==id`` and its previous versions.

        :URL: ``GET /morphologies/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            morphology whose history is requested.
        :returns: A dictionary of the form::

                {"morphology": { ... }, "previousVersions": [ ... ]}

            where the value of the ``morphology`` key is the morphology whose
            history is requested and the value of the ``previousVersions`` key
            is a list of dictionaries representing previous versions of the
            morphology.

        """
        morphology, previousVersions = h.getModelAndPreviousVersions('Morphology', id)
        if morphology or previousVersions:
            return {'morphology': morphology,
                    'previousVersions': previousVersions}
        else:
            response.status_int = 404
            return {'error': 'No morphologies or morphology backups match %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def compile(self, id):
        """Compile the script of a morphology as a foma FST.

        :URL: ``PUT /morphologies/compile/id``
        :param str id: the ``id`` value of the morphology whose script will be compiled.
        :returns: if the morphology exists and foma is installed, the morphology
            model is returned;  ``GET /morphologies/id`` must be polled to
            determine when and how the compilation task has terminated.

        .. note::

            The script is compiled asynchronously in a worker thread.  See 
            :mod:`onlinelinguisticdatabase.lib.worker`.

        """
        morphology = Session.query(Morphology).get(id)
        if morphology:
            if h.fomaInstalled():
                morphologyDirPath = getMorphologyDirPath(morphology)
                worker_q.put({
                    'id': h.generateSalt(),
                    'func': 'compileFomaScript',
                    'args': {'modelName': u'Morphology', 'modelId': morphology.id,
                        'scriptDirPath': morphologyDirPath, 'userId': session['user'].id,
                        'verificationString': u'defined morphology: ', 'timeout': h.morphologyCompileTimeout}
                })
                return morphology
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

    @h.restrict('GET')
    @h.authenticateWithJSON
    def servecompiled(self, id):
        """Serve the compiled foma script of the morphology.

        :URL: ``PUT /morphologies/servecompiled/id``
        :param str id: the ``id`` value of a morphology.
        :returns: a stream of bytes -- the compiled morphology script.  

        """
        morphology = Session.query(Morphology).get(id)
        if morphology:
            if h.fomaInstalled():
                fomaFilePath = getMorphologyFilePath(morphology, 'binary')
                if os.path.isfile(fomaFilePath):
                    return forward(FileApp(fomaFilePath))
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'Morphology %d has not been compiled yet.' % morphology.id})
            else:
                response.status_int = 400
                return json.dumps({'error': 'Foma and flookup are not installed.'})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no morphology with id %s' % id})

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def applydown(self, id):
        """Call foma apply down on the input in the request body using a morphology.

        :URL: ``PUT /morphologies/applydown/id``
        :param str id: the ``id`` value of the morphology that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply down.

        """
        return self.apply(id, 'down')

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def applyup(self, id):
        """Call foma apply up on the input in the request body using a morphology.

        :URL: ``PUT /morphologies/applyup/id``
        :param str id: the ``id`` value of the morphology that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply up.

        """
        return self.apply(id, 'up')

    def apply(self, id, direction):
        """Call foma apply in the direction of ``direction`` on the input in the request body using a morphology.

        :param str id: the ``id`` value of the morphology that will be used.
        :param str direction: the direction of foma application.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the morphology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            outputs of ``t1`` after apply up/down.

        """
        morphology = Session.query(Morphology).get(id)
        if morphology:
            if h.fomaInstalled():
                morphologyBinaryPath = getMorphologyFilePath(morphology, 'binary')
                if os.path.isfile(morphologyBinaryPath):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        inputs = MorphemeSequencesSchema.to_python(inputs)
                        return apply(direction, inputs['morphemeSequences'], morphology,
                                                 morphologyBinaryPath, session['user'])
                    except h.JSONDecodeError:
                        response.status_int = 400
                        return h.JSONDecodeErrorResponse
                    except Invalid, e:
                        response.status_int = 400
                        return {'errors': e.unpack_errors()}
                else:
                    response.status_int = 400
                    return {'error': 'Morphology %d has not been compiled yet.' % morphology.id}
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no morphology with id %s' % id}

def getDataForNewEdit(GET_params):
    """Return the data needed to create a new morphology or edit one."""
    modelNameMap = {'corpora': 'Corpus'}
    getterMap = {'corpora': h.getMiniDictsGetter('Corpus')}
    return h.getDataForNewAction(GET_params, getterMap, modelNameMap)

################################################################################
# Backup morphology
################################################################################

def backupMorphology(morphologyDict):
    """Backup a morphology.

    :param dict morphologyDict: a representation of a morphology model.
    :returns: ``None``

    """
    morphologyBackup = MorphologyBackup()
    morphologyBackup.vivify(morphologyDict)
    Session.add(morphologyBackup)


################################################################################
# Morphology Create & Update Functions
################################################################################

def createNewMorphology(data):
    """Create a new morphology.

    :param dict data: the data for the morphology to be created.
    :returns: an SQLAlchemy model object representing the morphology.

    """
    morphology = Morphology()
    morphology.UUID = unicode(uuid4())
    morphology.name = h.normalize(data['name'])
    morphology.description = h.normalize(data['description'])
    morphology.enterer = morphology.modifier = session['user']
    morphology.datetimeModified = morphology.datetimeEntered = h.now()
    morphology.lexiconCorpus = data['lexiconCorpus']
    morphology.rulesCorpus = data['rulesCorpus']
    morphology.script = generateMorphologyScript(morphology)
    return morphology

def updateMorphology(morphology, data):
    """Update a morphology.

    :param morphology: the morphology model to be updated.
    :param dict data: representation of the updated morphology.
    :returns: the updated morphology model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    changed = h.setAttr(morphology, 'name', h.normalize(data['name']), changed)
    changed = h.setAttr(morphology, 'description', h.normalize(data['description']), changed)
    changed = h.setAttr(morphology, 'lexiconCorpus', data['lexiconCorpus'], changed)
    changed = h.setAttr(morphology, 'rulesCorpus', data['rulesCorpus'], changed)
    changed = h.setAttr(morphology, 'script', generateMorphologyScript(morphology), changed)
    if changed:
        morphology.modifier = session['user']
        morphology.datetimeModified = h.now()
        return morphology
    return changed

def saveMorphologyScript(morphology):
    """Save the foma FST script of the morphology to ``morphology_<id>.script``.

    Also create the morphology compiler shell script, i.e., ``morphology_<id>.sh``
    which will be used to compile the morphology FST to a binary.

    :param morphology: a morphology model.
    :returns: the absolute path to the newly created morphology script file.

    """
    try:
        createMorphologyDir(morphology)
        morphologyScriptPath = getMorphologyFilePath(morphology, 'script')
        morphologyBinaryPath = getMorphologyFilePath(morphology, 'binary')
        morphologyCompilerPath = getMorphologyFilePath(morphology, 'compiler')
        with codecs.open(morphologyScriptPath, 'w', 'utf8') as f:
            f.write(morphology.script)
        # The compiler shell script loads the foma script and compiles it to binary form.
        with open(morphologyCompilerPath, 'w') as f:
            f.write('#!/bin/sh\nfoma -e "source %s" -e "regex morphology;" -e "save stack %s" -e "quit"' % (
                    morphologyScriptPath, morphologyBinaryPath))
        os.chmod(morphologyCompilerPath, 0744)
        return morphologyScriptPath
    except Exception:
        return None

class MorphologyScriptGenerationError(Exception):
    pass

def generateMorphologyScript(morphology):
    """Generate a foma script representing a morphology.

    :param morphology: an OLD morphology model
    :returns: a unicode object comprising the foma morphology script

    The lexicon corpus (``morphology.lexiconCorpus``) is used to extract 
    morphemes and create foma regexes of the form 'define noun = [c h a t"|cat":0|c h i e n"|dog":0];',
    i.e., mappings from 'chat' to 'chat|cat', etc.

    The rules corpus (``morphology.rulesCorpus``) is used to extract morphological
    rules in the form of POS templates and implement them all as a single foma regexe 
    of the form 'define morphology (noun "-" agr) | (noun);', i.e., an FST that maps,
    e.g., 'chat-s' to 'chat|cat-s|PL'.

    """
    unknownCategory = h.unknownCategory
    # Get a function that will split words into morphemes
    morphemeSplitter = lambda x: [x]
    morphemeDelimiters = h.getMorphemeDelimiters()
    if morphemeDelimiters:
        morphemeSplitter = re.compile(u'([%s])' % ''.join([h.escREMetaChars(d) for d in morphemeDelimiters])).split
    # Get the unique morphemes from the lexicon corpus
    morphemes = {}
    if (morphology.lexiconCorpus and
        morphology.lexiconCorpus.id != morphology.rulesCorpus.id):
        for form in morphology.lexiconCorpus.forms:
            newMorphemes = extractMorphemesFromForm(form, morphemeSplitter, unknownCategory)
            for POS, data in newMorphemes:
                morphemes.setdefault(POS, set()).add(data)
    # Get the POS strings (and morphemes) from the words in the rules corpus
    POSSequences = set()
    for form in morphology.rulesCorpus.forms:
        newPOSSequences, newMorphemes = extractWordPOSSequences(form, morphemeSplitter, unknownCategory)
        POSSequences |= newPOSSequences
        for POS, data in newMorphemes:
            morphemes.setdefault(POS, set()).add(data)
    lexiconScript = createLexiconScript(morphemes)
    rulesScript = createRulesScript(POSSequences)
    script = u'%s\n\n%s' % (lexiconScript, rulesScript)
    return script

def extractMorphemesFromForm(form, morphemeSplitter, unknownCategory):
    """Return the morphemes in the form as a tuple: (POS, (mb, mg)).
    """
    morphemes = []
    scWords = form.syntacticCategoryString.split()
    mbWords = form.morphemeBreak.split()
    mgWords = form.morphemeGloss.split()
    for scWord, mbWord, mgWord in zip(scWords, mbWords, mgWords):
        POSSequence = morphemeSplitter(scWord)[::2]
        morphemeSequence = morphemeSplitter(mbWord)[::2]
        glossSequence = morphemeSplitter(mgWord)[::2]
        for POS, morpheme, gloss in zip(POSSequence, morphemeSequence, glossSequence):
            if POS != unknownCategory:
                morphemes.append((POS, (morpheme, gloss)))
    return morphemes

def extractWordPOSSequences(form, morphemeSplitter, unknownCategory):
    """Return the unique word-based POS sequences, as well as the morphemes, implicit in the form.

    :param form: a form model object
    :param morphemeSplitter: callable that splits a strings into its morphemes and delimiters
    :param str unknownCategory: the string used in syntactic category strings when a morpheme-gloss pair is unknown
    :returns: 2-tuple: (set of POS/delimiter sequences, list of morphemes as (POS, (mb, mg)) tuples).

    """
    POSSequences = set()
    morphemes = []
    scWords = form.syntacticCategoryString.split()
    mbWords = form.morphemeBreak.split()
    mgWords = form.morphemeGloss.split()
    for scWord, mbWord, mgWord in zip(scWords, mbWords, mgWords):
        POSSequence = tuple(morphemeSplitter(scWord))
        if unknownCategory not in POSSequence:
            POSSequences.add(POSSequence)
            morphemeSequence = morphemeSplitter(mbWord)[::2]
            glossSequence = morphemeSplitter(mgWord)[::2]
            for POS, morpheme, gloss in zip(POSSequence[::2], morphemeSequence, glossSequence):
                morphemes.append((POS, (morpheme, gloss)))
    return POSSequences, morphemes

def createLexiconScript(morphemes):
    """Return a foma script defining a lexicon. 

    :param morphemes: dict from POSes to sets of (mb, mg) tuples.
    :returns: a unicode object that is a valid foma script defining a lexicon.

    .. note::

        The presence of a form of category N with a morpheme break value of 'chien' and
        a morpheme gloss value of 'dog' will result in the regex defined as 'N' having
        'c h i e n "|dog":0' as one of its disjuncts.  This is a transducer that maps
        'chien|dog' to 'chien', i.e,. '"|dog"' is a multi-character symbol that is mapped
        to the null symbol, i.e., '0'.  Note also that the vertical bar '|' character is 
        not actually used -- the delimiter character is actually that defined in ``utils.rareDelimiter``
        which, by default, is U+2980 'TRIPLE VERTICAL BAR DELIMITER'.

    .. warning::

        Foma reserved symbols are escaped in morpheme transcriptions (cf. ``h.escapeFomaReservedSymbols``
        below) and are removed from the names of defined regexes (cf. ``getValidFomaRegexName`` below).
        If removing reserved symbols from a name reduces it to the empty string, an exception is raised.

    """
    delimiter =  h.rareDelimiter
    regexes = []
    for POS, data in sorted(morphemes.items()):
        regex = [u'define %s [' % getValidFomaRegexName(POS)]
        lexicalItems = []
        for mb, mg in sorted(data):
            lexicalItems.append(u'    %s "%s%s":0' % (
                u' '.join(map(h.escapeFomaReservedSymbols, list(mb))), delimiter, mg))
        regex.append(u' |\n'.join(lexicalItems))
        regex.append(u'];\n')
        regexes.append(u'\n'.join(regex))
    return u'\n'.join(regexes)

def getValidFomaRegexName(candidate):
    """Return the candidate foma regex name with all reserved symbols removed and suffixed
    by "Cat".  This prevents conflicts between regex names and symbols in regexes.

    """
    name = h.deleteFomaReservedSymbols(candidate)
    if not name:
        raise Exception('The syntactic category name %s cannot be used as the name of a Foma regex since it contains only reserved symbols.' % name)
    return u'%sCat' % name

def posSequenceToFomaDisjunct(POSSequence):
    """Return a foma disjunct representing a POS sequence.

    :param tuple POSSequence: a tuple where the oddly indexed elements are 
        delimiters and the evenly indexed ones are POSes.
    :returns: a unicode object representing a foma disjunct, e.g., u'AGR "-" V'

    """
    tmp = []
    for index, element in enumerate(POSSequence):
        if index % 2 == 0:
            tmp.append(getValidFomaRegexName(element))
        else:
            tmp.append('"%s"' % element)
    return u' '.join(tmp)

def createRulesScript(POSSequences):
    """Return a foma script defining morphological rules.

    :param set POSSequences: tuples containing POSes and delimiters
    :returns: a unicode object that is a valid foma script defining morphological rules

    """
    regex = [u'define morphology (']
    disjuncts = []
    for POSSequence in sorted(POSSequences):
        disjuncts.append(u'    (%s)' % posSequenceToFomaDisjunct(POSSequence))
    regex.append(u' |\n'.join(disjuncts))
    regex.append(u');\n')
    return u'\n'.join(regex)

def createMorphologyDir(morphology):
    """Create the directory to hold the morphology script and auxiliary files.
    
    :param morphology: a morphology model object.
    :returns: an absolute path to the directory for the morphology.

    """
    morphologyDirPath = getMorphologyDirPath(morphology)
    h.makeDirectorySafely(morphologyDirPath)
    return morphologyDirPath

def getMorphologyDirPath(morphology):
    """Return the path to a morphology's directory.

    :param morphology: a morphology model object.
    :returns: an absolute path to the directory for the morphology.

    """
    return os.path.join(h.getOLDDirectoryPath('morphologies', config=config),
                        'morphology_%d' % morphology.id)

def getMorphologyFilePath(morphology, fileType='script'):
    """Return the path to a morphology's file of the given type.

    :param morphology: a morphology model object.
    :param str fileType: one of 'script', 'binary', 'compiler', or 'tester'.
    :returns: an absolute path to the morphology's script file.

    """
    extMap = {'script': 'script', 'binary': 'foma', 'compiler': 'sh', 'tester': 'tester.sh'}
    return os.path.join(getMorphologyDirPath(morphology),
            'morphology_%d.%s' % (morphology.id, extMap.get(fileType, 'script')))

def removeMorphologyDirectory(morphology):
    """Remove the directory of the morphology model and everything in it.
    
    :param morphology: a morphology model object.
    :returns: an absolute path to the directory for the morphology.

    """
    try:
        morphologyDirPath = getMorphologyDirPath(morphology)
        rmtree(morphologyDirPath)
        return morphologyDirPath
    except Exception:
        return None

def apply(direction, inputs, morphology, morphologyBinaryPath, user):
    """Foma-apply the inputs in the direction of ``direction`` using the morphology's compiled foma script.

    :param str direction: the direction in which to use the transducer
    :param list inputs: a list of morpho-phonemic transcriptions.
    :param morphology: a morphology model.
    :param str morphologyBinaryPath: an absolute path to a compiled morphology script.
    :param user: a user model.
    :returns: a dictionary: ``{input1: [o1, o2, ...], input2: [...], ...}``

    """
    randomString = h.generateSalt()
    morphologyDirPath = getMorphologyDirPath(morphology)
    inputsFilePath = os.path.join(morphologyDirPath,
            'inputs_%s_%s.txt' % (user.username, randomString))
    outputsFilePath = os.path.join(morphologyDirPath,
            'outputs_%s_%s.txt' % (user.username, randomString))
    applyFilePath = os.path.join(morphologyDirPath,
            'apply_%s_%s.sh' % (user.username, randomString))
    with codecs.open(inputsFilePath, 'w', 'utf8') as f:
        f.write(u'\n'.join(inputs))
    with codecs.open(applyFilePath, 'w', 'utf8') as f:
        f.write('#!/bin/sh\ncat %s | flookup %s%s' % (
            inputsFilePath, {'up': '', 'down': '-i '}.get(direction, '-i '), morphologyBinaryPath))
    os.chmod(applyFilePath, 0744)
    with open(os.devnull, 'w') as devnull:
        with codecs.open(outputsFilePath, 'w', 'utf8') as outfile:
            p = Popen(applyFilePath, shell=False, stdout=outfile, stderr=devnull)
    p.communicate()
    with codecs.open(outputsFilePath, 'r', 'utf8') as f:
        result = h.fomaOutputFile2Dict(f)
    os.remove(inputsFilePath)
    os.remove(outputsFilePath)
    os.remove(applyFilePath)
    return result

def getTests(morphology):
    """Return any tests defined in a morphology's script as a dictionary."""
    result = {}
    testLines = [l[6:] for l in morphology.script.splitlines() if l[:6] == u'#test ']
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


def runTests(morphology, morphologyBinaryPath, user):
    """Run the test defined in the morphology's script and return a report.
    
    :param morphology: a morphology model.
    :param str morphologyBinaryPath: an absolute path to the morphology's compiled foma script.
    :param user: a user model.
    :returns: a dictionary representing the report on the tests.

    A line in a morphology's script that begins with "#test " signifies a
    test.  After "#test " there should be a string of characters followed by
    "->" followed by another string of characters.  The first string is the
    underlying representation and the second is the anticipated surface
    representation.  Requests to ``GET /morphologies/runtests/id`` will cause
    the OLD to run a morphology script against its tests and return a
    dictionary detailing the expected and actual outputs of each input in the
    transcription.  :func:`runTests` generates that dictionary.

    """

    tests = getTests(morphology)
    if not tests:
        response.status_int = 400
        return {'error': 'The script of morphology %d contains no tests.' % morphology.id}
    results = morphologize(tests.keys(), morphology, morphologyBinaryPath, user)
    return dict([(t, {'expected': tests[t], 'actual': results[t]}) for t in tests])
