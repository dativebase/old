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

"""This module contains some multithreading worker and queue logic plus the functionality -- related
to foma compilation ang LM estimation -- that the worther thread initiates.

The the foma worker compiles foma FST phonology, morphology and morphophonology scripts
and estimates morpheme language models.  Having a worker perform these tasks in a separate
thread from that processing the HTTP request allows us to immediately respond to the user.

The foma worker can only run a callable that is a global in
:mod:`onlinelinguisticdatabase.lib.foma_worker` and which takes keyword arguments.
Example usage::

    from onlinelinguisticdatabase.lib.foma_worker import foma_worker_q
    foma_worker_q.put({
        'id': h.generate_salt(),
        'func': 'compile_foma_script',
        'args': {'model_name': u'Phonology', 'model_id': phonology.id,
            'script_dir_path': phonology_dir_path, 'user_id': session['user'].id,
            'verification_string': u'defined phonology: ', 'timeout': h.phonology_compile_timeout}
    })

Cf. http://www.chrismoos.com/2009/03/04/pylons-worker-threads.

For an introduction to Python threading, see
http://www.ibm.com/developerworks/aix/library/au-threadingpython/.

"""

import Queue
import threading
import logging
from uuid import uuid4
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.model as model

log = logging.getLogger(__name__)

################################################################################
# WORKER THREAD & QUEUE
################################################################################

foma_worker_q = Queue.Queue(1)

class FomaWorkerThread(threading.Thread):
    """Define the foma worker.
    """
    def run(self):
        while True:
            msg = foma_worker_q.get()
            try:
                globals()[msg.get('func')](**msg.get('args'))
            except Exception, e:
                log.warn('Unable to process in worker thread: %s' % e)
            foma_worker_q.task_done()

def start_foma_worker():
    """Called in :mod:`onlinelinguisticdatabase.config.environment.py`.
    """

    foma_worker = FomaWorkerThread()
    foma_worker.setDaemon(True)
    foma_worker.start()

    foma_worker2 = FomaWorkerThread()
    foma_worker2.setDaemon(True)
    foma_worker2.start()

################################################################################
# PHONOLOGY
################################################################################

def compile_phonology(**kwargs):
    """Compile the foma script of a phonology and save it to the db with values that indicating compilation success.
    """
    phonology = Session.query(model.Phonology).get(kwargs['phonology_id'])
    phonology.compile(kwargs['timeout'])
    phonology.datetime_modified = h.now()
    phonology.modifier_id = kwargs['user_id']
    Session.commit()

################################################################################
# MORPHOLOGY
################################################################################

def generate_and_compile_morphology(**kwargs):
    """Generate a foma script for a morphology and (optionally) compile it.

    :param int kwargs['morphology_id']: id of a morphology.
    :param bool kwargs['compile']: if True, the script will be generated *and* compiled.
    :param int kwargs['user_id']: id of the user model performing the generation/compilation.
    :param float kwargs['timeout']: how many seconds to wait before killing the foma compile process.

    """
    morphology = Session.query(model.Morphology).get(kwargs['morphology_id'])
    unknown_category = h.unknown_category
    try:
        morphology.write(unknown_category)
    except Exception, e:
        log.warn(e)
        pass
    if kwargs.get('compile', True):
        try:
            morphology.compile(kwargs['timeout'])
        except Exception, e:
            log.warn(e)
            pass
    morphology.generate_attempt = unicode(uuid4())
    morphology.modifier_id = kwargs['user_id']
    morphology.datetime_modified = h.now()
    Session.commit()

################################################################################
# MORPHEME LANGUAGE MODEL
################################################################################

def generate_language_model(**kwargs):
    """Write the requisite files (corpus, vocab, ARPA, LMTrie) of a morpheme LM to disk.

    :param str kwargs['morpheme_language_model_id']: ``id`` value of a morpheme LM.
    :param int/float kwargs['timeout']: seconds to allow for ARPA file creation.
    :param str kwargs['user_id']: ``id`` value of an OLD user.
    :returns: ``None``; side-effect is to change relevant attributes of LM object.

    """

    lm = Session.query(model.MorphemeLanguageModel).get(kwargs['morpheme_language_model_id'])
    trie_path = lm.get_file_path('trie')
    trie_mod_time = lm.get_modification_time(trie_path)
    lm.generate_succeeded = False
    try:
        lm.write_corpus()
    except Exception, e:
        lm.generate_message = u'Error writing the corpus file. %s' % e
    try:
        lm.write_vocabulary()
    except Exception, e:
        lm.generate_message = u'Error writing the vocabulary file. %s' % e
    try:
        lm.write_arpa(kwargs['timeout'])
    except Exception, e:
        lm.generate_message = u'Error writing the ARPA file. %s' % e
    try:
        lm.generate_trie()
    except Exception, e:
        lm.generate_message = u'Error generating the LMTrie instance. %s' % e
    else:
        if lm.get_modification_time(trie_path) != trie_mod_time:
            lm.generate_succeeded = True
            lm.generate_message = u'Language model successfully generated.'
        else:
            lm.generate_message = u'Error generating the LMTrie instance.'
    lm.generate_attempt = unicode(uuid4())
    lm.modifier_id = kwargs['user_id']
    lm.datetime_modified = h.now()
    Session.commit()

def compute_perplexity(**kwargs):
    """Evaluate the LM by attempting to calculate its perplexity and changing some attribute values to reflect the attempt.
    """
    lm = Session.query(model.MorphemeLanguageModel).get(kwargs['morpheme_language_model_id'])
    timeout = kwargs['timeout']
    iterations = 5
    try:
        lm.perplexity = lm.compute_perplexity(timeout, iterations)
    except Exception:
        lm.perplexity = None
    if lm.perplexity is None:
        lm.perplexity_computed = False
    else:
        lm.perplexity_computed = True
    lm.perplexity_attempt = unicode(uuid4())
    lm.modifier_id = kwargs['user_id']
    lm.datetime_modified = h.now()
    Session.commit()

################################################################################
# MORPHOLOGICAL PARSER (MORPHOPHONOLOGY)
################################################################################

def generate_and_compile_parser(**kwargs):
    """Write the parser's morphophonology FST script to file and compile it if ``compile_`` is True.
    Generate the language model and pickle it.

    """
    parser = Session.query(model.MorphologicalParser).get(kwargs['morphological_parser_id'])
    parser.changed = False
    parser.write()
    if kwargs.get('compile', True):
        parser.compile(kwargs['timeout'])
    parser.modifier_id = kwargs['user_id']
    parser.datetime_modified = h.now()
    if parser.changed:
        parser.cache.clear(persist=True)
    Session.commit()

