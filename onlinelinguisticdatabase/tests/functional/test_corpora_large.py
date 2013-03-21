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

import gzip
import StringIO
import re
import datetime
import logging
import os, sys
import codecs
import simplejson as json
from uuid import uuid4
from time import sleep
from nose.tools import nottest
from paste.deploy import appconfig
from sqlalchemy.sql import or_, and_, not_, asc, desc
from onlinelinguisticdatabase.tests import *
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h
import onlinelinguisticdatabase.lib.testutils as testutils
from onlinelinguisticdatabase.model import Corpus, CorpusBackup, CorpusFile
from subprocess import Popen, PIPE, call

log = logging.getLogger(__name__)

class TestCorporaLargeController(TestController):
    """Test the ``CorporaController`` making use of large "lorem ipsum" datasets."""

    config = appconfig('config:test.ini', relative_to='.')
    here = config['here']
    corpusPath = h.getOLDDirectoryPath('corpora', config=config)
    testCorporaPath = os.path.join(here, 'onlinelinguisticdatabase',
                        'tests', 'data', 'corpora')
    testScriptsPath = os.path.join(here, 'onlinelinguisticdatabase',
                        'tests', 'scripts')
    loremipsum100Path = os.path.join(testCorporaPath, 'loremipsum_100.txt')
    loremipsum1000Path = os.path.join(testCorporaPath, 'loremipsum_1000.txt')
    loremipsum10000Path = os.path.join(testCorporaPath, 'loremipsum_10000.txt')

    createParams = testutils.corpusCreateParams
    formCreateParams = testutils.formCreateParams
    syntacticCategoryCreateParams = testutils.syntacticCategoryCreateParams

    extra_environ_view = {'test.authentication.role': u'viewer'}
    extra_environ_contrib = {'test.authentication.role': u'contributor'}
    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    #@nottest
    def test_aaa_initialize(self):
        """Initialize the database using pseudo-data generated from random lorem ipsum sentences.

        These are located in ``onlinelinguisticdatabase/tests/data/corpora``.
        The data contain morphologically analyzed sentences, their component
        morphemes, and syntactic categories.  The sentences have phrase
        structure trees in bracket notation.

        The test will try to load the lorem ipsum dataset from a MySQL/SQLite
        dump file in ``onlinelinguisticdatabase/tests/data/corpora``.  If the
        dump file corresponding to ``loremipsumPath`` does not exist, it will
        import the lorem ipsum data directly from the text files and create
        the dump file so that future tests can run more speedily.  The
        ``loremipsum100Path``, ``loremipsum1000Path``, ``loremipsum10000Path``
        and ``loremipsum30000Path`` files are available and contain 100, 1000
        and 10,000 sentences, respectively.

        Setting the ``viaRequest`` variable to ``True`` will cause all of the
        forms to be created via request, i.e., via
        ``self.app.post(url('forms))...``.  This is much slower but may be
        desirable since values for the morphological analysis attributes
        will be generated.

        .. note::

            In order to run ``mysqldump`` with the MySQL user listed in
            ``test.ini``, that user must have permission to lock and update
            tables::

                mysql -u root -p<root_password>
                grant lock tables, update on old_test.* to 'old'@'localhost';

        .. warning::
        
            Loading the .txt or .sql files with the ``viaRequest`` option set to
            ``True`` will take a very long time.  This might be an argument for
            separating the interface and logic components of the controllers so
            that a "core" HTTP-less OLD application could be exposed.  This
            would facilitate the creation of models with system-generated data
            and validation but without the HTTP overhead...
            
        """

        ########################################################################
        # Configure lorem ipsum data set import
        ########################################################################

        # Set ``loremipsumPath`` this to ``self.loremipsum100Path``,
        # ``self.loremipsum1000Path`` or ``self.loremipsum10000Path``.
        # WARNING: the larger ones will take a long time.
        loremipsumPath = self.loremipsum1000Path 

        # Set ``viaRequest`` to ``True`` to create all forms via HTTP requests.
        viaRequest = True

        # S				sentential	
        def createModel(line, categories, viaRequest=False):
            """Create a model (form or syncat) using the string in ``line``."""
            model = 'Form'
            elements = unicode(line).split('\t')
            nonEmptyElements = filter(None, elements)
            lenNonEmptyElements = len(nonEmptyElements)
            try:
                ol, mb, mg, ml, sc, sx = nonEmptyElements
            except Exception:
                try:
                    ol, mb, mg, ml, sc = nonEmptyElements
                    sx = u''
                except Exception:
                    try:
                        model = 'SyntacticCategory'
                        n, t = nonEmptyElements
                    except Exception:
                        return categories
            if viaRequest:
                if model == 'SyntacticCategory':
                    params = self.syntacticCategoryCreateParams.copy()
                    params.update({
                        'name': n,
                        'type': t
                    })
                    params = json.dumps(params)
                    response = self.app.post(url('syntacticcategories'), params, self.json_headers,
                                  self.extra_environ_admin)
                    catId = json.loads(response.body)['id']
                    categories[n] = catId
                else:
                    params = self.formCreateParams.copy()
                    params.update({
                        'transcription': ol,
                        'morphemeBreak': mb,
                        'morphemeGloss': mg,
                        'translations': [{'transcription': ml, 'grammaticality': u''}],
                        'syntax': sx,
                        'syntacticCategory': categories.get(sc, u'')
                    })
                    params = json.dumps(params)
                    self.app.post(url('forms'), params, self.json_headers,
                                  self.extra_environ_admin)
            else:
                if model == 'SyntacticCategory':
                    syntacticCategory = model.SyntacticCategory()
                    syntacticCategory.name = n
                    syntacticCategory.type = t
                    Session.add(syntacticCategory)
                    categories[n] = syntacticCategory.id
                else:
                    form = model.Form()
                    form.transcription = ol
                    form.morphemeBreak = mb
                    form.morphemeGloss = mg
                    translation = model.Translation()
                    translation.transcription = ml
                    form.translations.append(translation)
                    form.syntax = sx
                    form.syntacticcategory_id = categories.get(sc, None)
                    Session.add(form)
            return categories

        def createModel_(line, sentenceCategoryId=None, viaRequest=False):
            """Create a model (form or syncat) using the string in ``line``."""
            try:
                ol, mb, mg, ml, sx = unicode(line).split('\t')
            except Exception:
                try:
                    ol, mb, mg, ml = unicode(line).split('\t')
                    sx = u''
                    sentenceCategoryId = None
                except Exception:
                    return
            if viaRequest:
                params = self.formCreateParams.copy()
                params.update({
                    'transcription': ol,
                    'morphemeBreak': mb,
                    'morphemeGloss': mg,
                    'translations': [{'transcription': ml, 'grammaticality': u''}],
                    'syntax': sx
                })
                if sentenceCategoryId:
                    params['syntacticCategory'] = sentenceCategoryId
                params = json.dumps(params)
                self.app.post(url('forms'), params, self.json_headers,
                              self.extra_environ_admin)
            else:
                form = model.Form()
                form.transcription = ol
                form.morphemeBreak = mb
                form.morphemeGloss = mg
                translation = model.Translation()
                translation.transcription = ml
                form.translations.append(translation)
                form.syntax = sx
                if sentenceCategoryId:
                    form.syntacticcategory_id = sentenceCategoryId
                Session.add(form)

        def addLoremipsumToDB(loremipsumPath, viaRequest=False):
            """Add the contents of the file at ``loremipsumPath`` to the database."""
            categories = {}
            with open(loremipsumPath, 'r') as f:
                i = 0
                for l in f:
                    if i % 100 == 0:
                        if not viaRequest: Session.commit()
                        log.debug('%d lines processed' % i)
                    i = i + 1
                    categories = createModel(l.replace('\n', ''), categories,
                                             viaRequest)
                Session.commit()

        loremipsumPathNoExt = os.path.splitext(loremipsumPath)[0]
        sqlalchemyURL = self.config['sqlalchemy.url']
        sqlalchemyURLList = sqlalchemyURL.split(':')
        olddumpScriptPath = os.path.join(self.testScriptsPath, 'olddump.sh')
        oldloadScriptPath = os.path.join(self.testScriptsPath, 'oldload.sh')
        RDBMS = sqlalchemyURLList[0]

        if RDBMS == 'mysql':
            mysqlDumpPath = '%s_mysql.sql' % loremipsumPathNoExt
            username = sqlalchemyURLList[1][2:]
            password = sqlalchemyURLList[2].split('@')[0]
            dbname = sqlalchemyURLList[3].split('/')[1]
            if os.path.exists(mysqlDumpPath):
                log.debug('The lorem ipsum MySQL dump file exists.  Loading it...')
                # Clear the current DB completely
                h.clearAllModels(retain=[])
                # Load the dump file to the DB
                shellScript = '#!/bin/sh\nmysql -u %s -p%s %s < %s' % (
                    username, password, dbname, mysqlDumpPath)
                with open(oldloadScriptPath, 'w') as f:
                    f.write(shellScript)
                os.chmod(oldloadScriptPath, 0744)
                # Load the DB
                with open(os.devnull, 'w') as f:
                    call([oldloadScriptPath], stdout=f, stderr=f)
                # Destroy the load script
                os.remove(oldloadScriptPath)
                log.debug('Loaded.')
            else:
                log.debug('Have to import the lorem ipsum dataset from the text file and create the MySQL dump file.')
                # Populate the database from the loremipusm text file and dump it
                addLoremipsumToDB(loremipsumPath, viaRequest=viaRequest)
                # Write the DB dump shell script
                shellScript = '#!/bin/sh\nmysqldump -u %s -p%s --no-create-info %s > %s' % (
                    username, password, dbname, mysqlDumpPath)
                with open(olddumpScriptPath, 'w') as f:
                    f.write(shellScript)
                os.chmod(olddumpScriptPath, 0744)
                # Dump the DB
                with open(os.devnull, 'w') as f:
                    call([olddumpScriptPath], stdout=f, stderr=f)
                # Destroy the dump script
                os.remove(olddumpScriptPath)
                log.debug('Imported and dumped.')
        elif RDBMS == 'sqlite' and h.commandLineProgramInstalled('sqlite3'):
            sqliteDumpPath = '%s_sqlite.sql' % loremipsumPathNoExt
            sqliteDB = sqlalchemyURL.split('/')[-1]
            dbpath = os.path.join(self.here, sqliteDB)
            if os.path.exists(sqliteDumpPath):
                log.debug('The lorem ipsum SQLite dump file exists.  Loading it...')
                # Clear the current DB completely
                h.clearAllModels(retain=[])
                # Load the dump file to the DB
                shellScript = '#!/bin/sh\nsqlite3 %s < %s' % (
                    dbpath, sqliteDumpPath)
                with open(oldloadScriptPath, 'w') as f:
                    f.write(shellScript)
                os.chmod(oldloadScriptPath, 0744)
                # Load the DB
                with open(os.devnull, 'w') as f:
                    call([oldloadScriptPath], stdout=f, stderr=f)
                # Destroy the load script
                os.remove(oldloadScriptPath)
                log.debug('Loaded.')
            else:
                log.debug('Have to import the lorem ipsum dataset from the text file and create the SQLite dump file.')
                # Populate the database from the loremipusm text file and dump it
                addLoremipsumToDB(loremipsumPath, viaRequest=viaRequest)
                # Write the DB dump shell script
                shellScript = '#!/bin/sh\nsqlite3 %s ".dump" | grep -v "^CREATE" > %s' % (
                    dbpath, sqliteDumpPath)
                with open(olddumpScriptPath, 'w') as f:
                    f.write(shellScript)
                os.chmod(olddumpScriptPath, 0744)
                # Dump the DB
                with open(os.devnull, 'w') as f:
                    call([olddumpScriptPath], stdout=f, stderr=f)
                # Destroy the dump script
                os.remove(olddumpScriptPath)
                log.debug('Imported and dumped.')
        forms = h.getForms()
        log.debug('Lorem ipsum data loaded.  There are now %d forms in the db.' % len(forms))

        # Restrict one sentential form in the db.
        restrictedTag = h.generateRestrictedTag()
        Session.add(restrictedTag)
        Session.commit()
        restrictedTagId = restrictedTag.id
        aForm = Session.query(model.Form).\
            filter(model.Form.syntacticCategory.\
                has(model.SyntacticCategory.name==u'S')).first()
        aFormId = aForm.id
        aForm.tags.append(restrictedTag)
        Session.commit()
        restrictedForm = Session.query(model.Form).\
            filter(model.Form.tags.any(model.Tag.name==u'restricted')).first()
        assert aFormId == restrictedForm.id

    #@nottest
    def test_writetofile_all_sentences(self):
        """Tests file writing/retrieval of a corpus containing all sentences.

        That is, that ``PUT /corpora/id/writetofile`` and
        ``GET /corpora/id/servefile`` both work with a corpus defined by a form
        search model that returns all sentences.

        """

        # Create a form search model that retrieves all sentences
        query = {'filter': ['Form', 'syntacticCategory', 'name', '=', 'S']}
        params = json.dumps({
            'name': u'Get all sentences',
            'description': u'Query to return all sentences in the database.',
            'search': query
        })
        response = self.app.post(url('formsearches'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        formSearchId = resp['id']

        # Perform the search to get the resulting forms.
        params = json.dumps({
            'query': query,
            'paginator': {'page': 1, 'itemsPerPage': 1}})
        response = self.app.post(url('/forms/search'), params,
                                 self.json_headers, self.extra_environ_admin)
        resp = json.loads(response.body)
        sentenceCount = resp['paginator']['count']
        aTree = resp['items'][0]['syntax']

        # Generate some valid corpus creation input parameters.
        params = self.createParams.copy()
        params.update({
            'name': u'Corpus of sentences',
            'description': u'No ordering, no duplicates.',
            'formSearch': formSearchId
        })
        params = json.dumps(params)

        # Create the corpus
        #assert os.listdir(self.corpusPath) == []
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusId = resp['id']
        newCorpusCount = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        assert newCorpusCount == originalCorpusCount + 1
        assert resp['name'] == u'Corpus of sentences'
        assert resp['description'] == u'No ordering, no duplicates.'
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == u''
        assert corpus.forms == []
        assert resp['formSearch']['id'] == formSearchId

        # Write the corpus to file
        sleep(1)
        params = json.dumps({'format': 'treebank'})
        response = self.app.put(url('/corpora/%d/writetofile' % corpusId), params,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp2 = json.loads(response.body)
        corpusDirContents = os.listdir(corpusDir)
        corpusTbkPath = os.path.join(corpusDir, 'corpus_%d.tbk' % corpusId)
        corpusTbkGzippedPath = '%s.gz' % corpusTbkPath
        corpusTbkFileLength = h.getFileLength(corpusTbkPath)
        corpusFileId = resp2['files'][0]['id']
        assert resp['id'] == resp2['id']
        assert resp['name'] == resp2['name']
        assert resp2['datetimeModified'] > resp['datetimeModified']
        assert os.path.exists(corpusTbkPath)
        assert os.path.exists(corpusTbkGzippedPath)
        assert testutils.getFileSize(corpusTbkPath) > testutils.getFileSize(
                                                        corpusTbkGzippedPath)
        assert sentenceCount == corpusTbkFileLength

        # Retrieve the corpus file directly from the filesystem.
        corpusFileObject = open(corpusTbkPath, 'r')
        corpusFileContent = corpusFileObject.read()

        # Attempt to retrieve the gzipped corpus file via request as a restricted
        # user and expect to fail.  This is because there is one restricted
        # sentential form in the db, cf. the ``initialize`` "test".
        response = self.app.get(url('/corpora/%d/servefile/%d' % (
            corpusId, corpusFileId)), params, status=403,
            headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == h.unauthorizedMsg

        # Retrieve the gzipped corpus file via request.
        response = self.app.get(url('/corpora/%d/servefile/%d' % (
            corpusId, corpusFileId)), params,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        unzippedCorpusFileContent = testutils.decompressGzipString(response.body)
        assert unzippedCorpusFileContent == corpusFileContent


    #@nottest
    def test_writetofile_content_specified(self):
        """Tests file writing/retrieval of a corpus whose forms are specified in the ``content`` attribute.

        """

        # Get ids of all sentences.
        sentences = Session.query(model.Form).\
            filter(model.Form.syntacticCategory.\
                has(model.SyntacticCategory.name==u'S')).all()
        lenSentences = len(sentences)
        sentences = '\n'.join(['form[%d]' % f.id for f in sentences])

        # Get ids of all sentences with more than 5 words.
        longSentences = Session.query(model.Form).\
            filter(and_(
                model.Form.syntacticCategory.has(model.SyntacticCategory.name==u'S'),
                model.Form.transcription.op('regexp')(u'^([^ ]+ ){5}[^ ]+'))).all()
        lenLongSentences = len(longSentences)
        longSentences = '\n'.join(['form[%d]' % f.id for f in longSentences])

        content = '\n'.join([sentences, longSentences, longSentences, longSentences])
        anticipatedLength = lenSentences + (3 * lenLongSentences)
        name = u'Corpus of sentences with 6+ word sentences repeated'
        description = u'Ordered by content field; duplicates of words with more than 6 words.'

        # Generate some valid corpus creation input parameters.
        params = self.createParams.copy()
        params.update({
            'name': name,
            'description': description,
            'content': content
        })
        params = json.dumps(params)

        # Create the corpus
        originalCorpusCount = Session.query(Corpus).count()
        response = self.app.post(url('corpora'), params, self.json_headers,
                                 self.extra_environ_admin)
        resp = json.loads(response.body)
        corpusId = resp['id']
        newCorpusCount = Session.query(Corpus).count()
        corpus = Session.query(Corpus).get(corpusId)
        corpusDir = os.path.join(self.corpusPath, 'corpus_%d' % corpusId)
        corpusDirContents = os.listdir(corpusDir)
        assert newCorpusCount == originalCorpusCount + 1
        assert resp['name'] == name
        assert resp['description'] == description
        assert corpusDirContents == []
        assert response.content_type == 'application/json'
        assert resp['content'] == content
        # The ``forms`` attribute is a collection, no repeats, that's why the following is true:
        assert len(corpus.forms) == lenSentences

        # Write the corpus to file as a treebank
        sleep(1)
        params = json.dumps({u'format': u'treebank'})
        response = self.app.put(url('/corpora/%d/writetofile' % corpusId), params,
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        resp2 = json.loads(response.body)
        corpusDirContents = os.listdir(corpusDir)
        corpusTbkPath = os.path.join(corpusDir, 'corpus_%d.tbk' % corpusId)
        corpusTbkGzippedPath = '%s.gz' % corpusTbkPath
        corpusTbkGzippedSize = testutils.getFileSize(corpusTbkGzippedPath)
        corpusTbkFileLength = h.getFileLength(corpusTbkPath)
        corpusFileId = resp2['files'][0]['id']
        assert resp['id'] == resp2['id']
        assert resp['name'] == resp2['name']
        assert resp2['datetimeModified'] > resp['datetimeModified']
        assert os.path.exists(corpusTbkPath)
        assert os.path.exists(corpusTbkGzippedPath)
        assert testutils.getFileSize(corpusTbkPath) > corpusTbkGzippedSize
        assert anticipatedLength == corpusTbkFileLength
        log.debug(h.prettyPrintBytes(corpusTbkGzippedSize))
        log.debug(anticipatedLength)

        # Retrieve the corpus file directly from the filesystem.
        corpusFileObject = open(corpusTbkPath, 'r')
        corpusFileContent = corpusFileObject.read()

        # Attempt to retrieve the gzipped corpus file via request as a restricted
        # user and expect to fail.
        response = self.app.get(url('/corpora/%d/servefile/%d' % (
            corpusId, corpusFileId)), status=403,
            headers=self.json_headers, extra_environ=self.extra_environ_contrib)
        resp = json.loads(response.body)
        assert resp == h.unauthorizedMsg

        # Retrieve the gzipped corpus file via request.
        response = self.app.get(url('/corpora/%d/servefile/%d' % (
            corpusId, corpusFileId)),
            headers=self.json_headers, extra_environ=self.extra_environ_admin)
        assert len(response.body) < len(corpusFileContent)
        unzippedCorpusFileContent = testutils.decompressGzipString(response.body)
        assert unzippedCorpusFileContent == corpusFileContent

    #@nottest
    def test_zzz_cleanup(self):
        """Clean up after the tests."""
        # Destruction
        h.clearAllTables()
        h.destroyAllUserDirectories()
        h.destroyAllCorpusDirectories()
        # Creation
        languages = h.getLanguageObjects('test.ini', self.config)
        administrator = h.generateDefaultAdministrator()
        contributor = h.generateDefaultContributor()
        viewer = h.generateDefaultViewer()
        Session.add_all([administrator, contributor, viewer] + languages)
        Session.commit()
