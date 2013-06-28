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
to foma compilation ang LM estimation -- that the worther thread initiates.  Foma worker thread and queue for the OLD.

The the foma worker compiles foma FST phonology, morphology and morphophonology scripts
and estimates morpheme language models.  Having a worker perform these tasks in a separate
thread from that processing the request allows us to immediately respond to the user.

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
import os
import re
import cPickle
import codecs
try:
    import ujson as json
except ImportError:
    import simplejson as json
import hashlib
from uuid import uuid4
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.model as model
import onlinelinguisticdatabase.lib.simplelm as simplelm
from subprocess import Popen, PIPE
from signal import SIGKILL
import random

log = logging.getLogger(__name__)

foma_worker_q = Queue.Queue()

################################################################################
# WORKER
################################################################################

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

################################################################################
# SUBPROCESS CONTROL
################################################################################

class Command(object):
    """Runs the input command ``cmd`` as a subprocess within a thread.

    Pass a ``timeout`` argument to :func:`Command.run` and the process running
    the input ``cmd`` will be terminated at the end of that time if it hasn't
    terminated on its own.

    Cf. http://stackoverflow.com/questions/1191374/subprocess-with-timeout

    """
    def __init__(self, cmd, logpath=None):
        self.cmd = cmd
        self.logpath = logpath
        self.process = None

    def run(self, timeout):
        """Run :func:`self.cmd` as a subprocess that is terminated within ``timeout`` seconds.

        :param float timeout: time in seconds by which :func:`self.cmd` will be terminated.
        :return: 2-tuple: return code of process, stdout

        """
        def target():
            with open(self.logpath or os.devnull, "w") as logfile:
                self.process = Popen(self.cmd, stdout=logfile, stderr=logfile)
            self.process.communicate()
        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            self.kill_process(self.process)
            thread.join()
        try:
            stdout = open(self.logpath).read()
        except Exception:
            stdout = ''
        return self.process.returncode, stdout

    def kill_process(self, process):
        pid = process.pid
        pids = [pid]
        pids.extend(self.get_process_children(pid))
        for pid in pids:
            try: 
                os.kill(pid, SIGKILL)
            except OSError:
                pass

    def get_process_children(self, pid):
        p = Popen('ps --no-headers -o pid --ppid %d' % pid, shell=True,
                  stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        return [int(p) for p in stdout.split()]

################################################################################
# FOMA
################################################################################

def compile_foma_script(**kwargs):
    """Compile the foma script of an OLD model (a phonology or a morphology).

    The :class:`Command` performs the compilation and cancels it if it exceeds ``kwargs['timeout']`` seconds.

    :param kwargs['model_object']: a phonology or morphology model object.
    :param str kwargs['verification_string']: a string that will be found in the stdout of a successful foma request.
    :param str kwargs['script_dir_path']: the absolute path to the model's script directory.
    :param int kwargs['user_id']: a user model's ``id`` value.
    :param float/int kwargs['timeout']: how long to wait before terminating the compile process.
    :returns: the model object with new values for its compile_attempt, compile_succeeded, compile_message,
        modifier and datetime_modified attributes.

    """
    model_object = kwargs.get('model_object')
    verification_string = kwargs.get('verification_string')
    script_dir_path = kwargs.get('script_dir_path')
    timeout = kwargs.get('timeout', 30)
    compiler_path = kwargs.get('compiler_path', h.get_model_file_path(model_object, script_dir_path, 'compiler'))
    binary_path = kwargs.get('binary_path', h.get_model_file_path(model_object, script_dir_path, 'binary'))
    log_path = kwargs.get('log_path', h.get_model_file_path(model_object, script_dir_path, 'log'))
    binary_mod_time = h.get_modification_time(binary_path)
    try:
        command = Command([compiler_path], log_path)
        returncode, output = command.run(timeout=timeout)
        if verification_string in output:
            if returncode == 0:
                if (os.path.isfile(binary_path) and
                    binary_mod_time != h.get_modification_time(binary_path)):
                    model_object.compile_succeeded = True
                    model_object.compile_message = u'Compilation process terminated successfully and new binary file was written.'
                else:
                    model_object.compile_succeeded = False
                    model_object.compile_message = u'Compilation process terminated successfully yet no new binary file was written.'
            else:
                model_object.compile_succeeded = False
                model_object.compile_message = u'Compilation process failed.'
        else:
            model_object.compile_succeeded = False
            model_object.compile_message = u'Foma script is not a well-formed %s.' % model_object.__tablename__
    except Exception:
        model_object.compile_succeeded = False
        model_object.compile_message = u'Compilation attempt raised an error.'
    if model_object.compile_succeeded:
        os.chmod(binary_path, 0744)
    else:
        try:
            os.remove(binary_path)
        except Exception:
            pass
    return model_object

################################################################################
# PHONOLOGY
################################################################################

def compile_phonology_script(**kwargs):
    """Compile the foma script of a phonology and save it to the db with values that indicating compilation success.
    """
    phonology_id = kwargs['phonology_id']
    phonology = Session.query(model.Phonology).get(phonology_id)
    kwargs['model_object'] = phonology
    phonology = compile_foma_script(**kwargs)
    phonology.datetime_modified = h.now()
    phonology.modifier_id = kwargs['user_id']
    phonology.compile_attempt = unicode(uuid4())
    Session.commit()

################################################################################
# MORPHOLOGICAL PARSER (MORPHOPHONOLOGY)
################################################################################

def create_morphological_parser_components(**kwargs):
    """Write the parser's morphophonology FST script to file and compile it if ``compile_`` is True.
    Generate the language model and pickle it.

    """
    morphological_parser_id = kwargs.get('morphological_parser_id')
    script_dir_path = kwargs.get('script_dir_path')
    morphology_dir_path = kwargs.get('morphology_dir_path')
    morphological_parser = Session.query(model.MorphologicalParser).get(morphological_parser_id)
    morpheme_delimiters = h.get_morpheme_delimiters()
    kwargs.update({
        'model_object': morphological_parser,
        'morphological_parser': morphological_parser,
        'script_path': h.get_model_file_path(morphological_parser, script_dir_path, 'script'),
        'binary_path': h.get_model_file_path(morphological_parser, script_dir_path, 'binary'),
        'compiler_path': h.get_model_file_path(morphological_parser, script_dir_path, 'compiler'),
        'log_path': h.get_model_file_path(morphological_parser, script_dir_path, 'log'),
        'language_model_path': h.get_model_file_path(morphological_parser, script_dir_path, 'language_model'),
        'morpheme_delimiters': morpheme_delimiters
    })
    write_morphophonology_script_to_disk(**kwargs)
    if kwargs.get('compile', True):
        morphological_parser = compile_foma_script(**kwargs)
        morphological_parser.compile_attempt = unicode(uuid4())
    morphological_parser.generate_attempt = unicode(uuid4())
    morphological_parser.modifier_id = kwargs['user_id']
    morphological_parser.datetime_modified = h.now()
    Session.commit()

def write_morphophonology_script_to_disk(**kwargs):
    try:
        _write_morphophonology_script_to_disk(**kwargs)
    except Exception:
        pass

def _write_morphophonology_script_to_disk(**kwargs):
    """Write the foma FST script of the morphophonology to file.

    Also create the morphophonology compiler shell script, i.e., ``morphophonology_<id>.sh``
    which will be used to compile the morphophonology FST to a binary.

    :param kwargs['morphological_parser']: a morphological parser model.
    :param str kwargs['script_path']: absolute path to the parser's morphophonology script file.
    :param str kwargs['binary_path']: absolute path to the parser's morphophonology binary foma file.
    :param str kwargs['compiler_path']: absolute path to the shell script that compiles the script to the binary.
    :returns: None

    The morphophonology is defined via the following procedure:
    1. load the lexc morphology and define 'morphology' from it OR copy the entire script of the regex morphology
    2. copy in the phonology script, replacing 'define phonology ...' with 'define morphophonology .o. morphology ...'.

    """

    def generate_morphophonology(phonology_script):
        """Return the phonology script with 'define phonology ...' replaced by 'define morphophonology morphology .o. ...'"""
        phonology_definition_patt = re.compile('define( )+phonology( )+.+?[^%"];', re.DOTALL)
        define_phonology_patt = re.compile('define( )+phonology')
        if phonology_definition_patt.search(phonology_script):
            return define_phonology_patt.sub('define morphophonology morphology .o. ', phonology_script)
        return None

    morphological_parser = kwargs['morphological_parser']
    script_path = kwargs['script_path']
    binary_path = kwargs['binary_path']
    compiler_path = kwargs['compiler_path']
    with open(compiler_path, 'w') as f:
        f.write('#!/bin/sh\nfoma -e "source %s" -e "regex morphophonology;" -e "save stack %s" -e "quit"' % (
                    script_path, binary_path))
    os.chmod(compiler_path, 0744)
    morphology_script_path = h.get_model_file_path(morphological_parser.morphology, kwargs['morphology_dir_path'], 'script')
    #h.get_model_file_path(model_object, script_dir_path, file_type='script'):
    phonology_script = morphological_parser.phonology.script
    morphophonology = generate_morphophonology(phonology_script)
    if morphophonology:
        with codecs.open(script_path, 'w', 'utf8') as f:
            if morphological_parser.morphology.script_type == 'lexc':
                f.write('read lexc %s\n\n' % morphology_script_path)
                f.write('define morphology;\n\n')
            else:
                f.write('source %s\n\n' % morphology_script_path)
            f.write('define morphology "%s" morphology "%s";\n\n' % (h.word_boundary_symbol, h.word_boundary_symbol))
            f.write('%s\n' % morphophonology)
    else:
        with codecs.open(script_path, 'w', 'utf8') as f:
            # Default morphophonology is the identity function.
            f.write('define morphophonology ?*;\n')

################################################################################
# MORPHOLOGY
################################################################################

def generate_and_compile_morphology_script(**kwargs):
    """Generate a foma script for a morphology and (optionally) compile it.

    :param bool compile: if True, the script will be generated *and* compiled.
    :param int morphology_id: id of a morphology.
    :param str script_dir_path: absolute path to directory for saving script, e.g., /home/old/store/morphologies/morphology_26.
    :param int user_id: id of the user model performing the generation/compilation.
    :param str verification_string: subsequence of stdout to expect from foma compilation attempt.
    :param float timeout: how many seconds to wait before killing the foma compile process.

    """
    morphology_id = kwargs.get('morphology_id')
    script_dir_path = kwargs.get('script_dir_path')
    morphology = Session.query(model.Morphology).get(morphology_id)
    morpheme_delimiters = h.get_morpheme_delimiters()
    rules, lexicon = get_rules_and_lexicon(morphology, morpheme_delimiters)
    kwargs.update({
        'model_object': morphology,
        'morphology': morphology,
        'script_path': h.get_model_file_path(morphology, script_dir_path, 'script'),
        'binary_path': h.get_model_file_path(morphology, script_dir_path, 'binary'),
        'compiler_path': h.get_model_file_path(morphology, script_dir_path, 'compiler'),
        'log_path': h.get_model_file_path(morphology, script_dir_path, 'log'),
        'pos_sequences': rules,
        'morphemes': lexicon,
        'morpheme_delimiters': morpheme_delimiters
    })
    write_morphology_script_to_disk(**kwargs)
    morphology.rules_generated = u' '.join(map(u''.join, rules))
    # pickle the lexicon dict
    lexicon_path = h.get_model_file_path(morphology, script_dir_path, 'lexicon')
    cPickle.dump(lexicon, open(lexicon_path, 'wb'))
    if kwargs.get('compile', True):
        morphology = compile_foma_script(**kwargs)
        morphology.compile_attempt = unicode(uuid4())
    morphology.generate_attempt = unicode(uuid4())
    morphology.modifier_id = kwargs['user_id']
    morphology.datetime_modified = h.now()
    Session.commit()

def get_rules_and_lexicon(morphology, morpheme_delimiters):
    try:
        return _get_rules_and_lexicon(morphology, morpheme_delimiters)
    except Exception:
        return [], {}

def _get_rules_and_lexicon(morphology, morpheme_delimiters):
    """Return the rules (i.e., POS sequences) and lexicon (i.e., morphemes) entailed by a morphology.

    """
    def extract_morphemes_from_form(form, morpheme_splitter, unknown_category):
        """Return the morphemes in the form as a tuple: (pos, (mb, mg))."""
        morphemes = []
        if not form.syntactic_category_string:
            return morphemes
        sc_words = form.syntactic_category_string.split()
        mb_words = form.morpheme_break.split()
        mg_words = form.morpheme_gloss.split()
        for sc_word, mb_word, mg_word in zip(sc_words, mb_words, mg_words):
            pos_sequence = morpheme_splitter(sc_word)[::2]
            morpheme_sequence = morpheme_splitter(mb_word)[::2]
            gloss_sequence = morpheme_splitter(mg_word)[::2]
            for pos, morpheme, gloss in zip(pos_sequence, morpheme_sequence, gloss_sequence):
                if pos != unknown_category:
                    morphemes.append((pos, (morpheme, gloss)))
        return morphemes

    def filter_invalid_sequences(pos_sequences, morphemes, morphology, morpheme_delimiters):
        """Remove category sequences from pos_sequences if they contain categories not listed as 
        keys of the morphemes dict or if they contain delimiters not listed in morpheme_delimiters.
        """
        if not morphemes:
            return pos_sequences
        if morphology.extract_morphemes_from_rules_corpus:
            return pos_sequences
        valid_elements = set(morphemes.keys() + morpheme_delimiters)
        new_pos_sequences = set()
        for pos_sequence in pos_sequences:
            pos_sequence_set = set(pos_sequence)
            if pos_sequence_set & valid_elements == pos_sequence_set:
                new_pos_sequences.add(pos_sequence)
        return new_pos_sequences

    unknown_category = h.unknown_category
    # Get a function that will split words into morphemes
    morpheme_splitter = h.get_morpheme_splitter()
    # Get the unique morphemes from the lexicon corpus
    morphemes = {}
    if (morphology.lexicon_corpus and
        (not morphology.rules_corpus or
        morphology.lexicon_corpus.id != morphology.rules_corpus.id)):
        for form in morphology.lexicon_corpus.forms:
            new_morphemes = extract_morphemes_from_form(form, morpheme_splitter, unknown_category)
            for pos, data in new_morphemes:
                morphemes.setdefault(pos, set()).add(data)
    # Get the pos sequences (and morphemes) from the use-specified ``rules`` string value or else from the 
    # words in the rules corpus.
    pos_sequences = set()
    if morphology.rules:
        for pos_sequence_string in morphology.rules.split():
            pos_sequence = tuple(morpheme_splitter(pos_sequence_string))
            pos_sequences.add(pos_sequence)
    else:
        for form in morphology.rules_corpus.forms:
            new_pos_sequences, new_morphemes = h.extract_word_pos_sequences(form, unknown_category,
                                morpheme_splitter, morphology.extract_morphemes_from_rules_corpus)
            if new_pos_sequences:
                pos_sequences |= new_pos_sequences
                for pos, data in new_morphemes:
                    morphemes.setdefault(pos, set()).add(data)
    pos_sequences = filter_invalid_sequences(pos_sequences, morphemes, morphology, morpheme_delimiters)
    # sort and delistify the rules and lexicon
    pos_sequences = sorted(pos_sequences)
    morphemes = dict([(pos, sorted(data)) for pos, data in morphemes.iteritems()])
    return pos_sequences, morphemes

def write_morphology_script_to_disk(**kwargs):
    try:
        _write_morphology_script_to_disk(**kwargs)
    except Exception:
        pass

def _write_morphology_script_to_disk(**kwargs):
    """Write the foma FST script of the morphology to file.

    Also create the morphology compiler shell script, i.e., ``morphology_<id>.sh``
    which will be used to compile the morphology FST to a binary.

    :param kwargs['morphology']: a morphology model.
    :param set kwargs['pos_sequences']: tuples containing sequences of categories and morpheme delimiters
    :param dict kwargs['morphemes']: keys are categories, values are sets of (form, gloss) 2-tuples
    :param list kwargs['morpheme_delimiters']: unicode strings that are used to delimit morphemes
    :param str kwargs['script_path']: absolute path to the morphology's script file.
    :param str kwargs['binary_path']: absolute path to the morphology's binary foma file.
    :param str kwargs['compiler_path']: absolute path to the shell script that compiles the script to the binary.
    :returns: None

    .. note::

        We do not generate and return the morphology foma script because we do not 
        store it in the db, we simply save it to disk.  The reason for this is the 
        potentially huge size of the script generated, i.e., tens of MB.

    """
    morphology = kwargs['morphology']
    pos_sequences = kwargs['pos_sequences']
    morphemes = kwargs['morphemes']
    morpheme_delimiters = kwargs['morpheme_delimiters']
    script_path = kwargs['script_path']
    binary_path = kwargs['binary_path']
    compiler_path = kwargs['compiler_path']
    with open(compiler_path, 'w') as f:
        if morphology.script_type == 'lexc':
            f.write('#!/bin/sh\nfoma -e "read lexc %s" -e "save stack %s" -e "quit"' % (
                    script_path, binary_path))
        else:
            f.write('#!/bin/sh\nfoma -e "source %s" -e "regex morphology;" -e "save stack %s" -e "quit"' % (
                    script_path, binary_path))
    os.chmod(compiler_path, 0744)
    with codecs.open(script_path, 'w', 'utf8') as f:
        morphology_generator = get_morphology_generator(morphology, pos_sequences, morphemes, morpheme_delimiters)
        for line in morphology_generator:
            f.write(line)

def get_morphology_generator(morphology, pos_sequences, morphemes, morpheme_delimiters):
    """Return a generator that yields lines of a foma morphology script.

    :param morphology: an OLD morphology model
    :param list pos_sequences: a sorte list of tuples containing sequences of categories and morpheme delimiters
    :param dict morphemes: keys are categories, values are lists of (form, gloss) 2-tuples
    :param list morpheme_delimiters: unicode strings that are used to delimit morphemes
    :returns: generator object that yields lines of a foma morphology script

    """
    if morphology.script_type == 'lexc':
        return get_lexc_morphology_generator(morphemes, pos_sequences, morpheme_delimiters)
    else:
        return get_regex_morphology_generator(morphemes, pos_sequences)

def get_lexc_morphology_generator(morphemes, pos_sequences, morpheme_delimiters):
    """Return a generator that yields lines of a foma script representing the morphology using the lexc formalism,
    cf. https://code.google.com/p/foma/wiki/MorphologicalAnalysisTutorial.

    :param dict morphemes: a dict from category names to lists of (form, gloss) tuples.
    :param list pos_sequences: a sorted list of tuples containing category names and morpheme delimiters.
    :yields: lines of a lexc foma script

    The OLD generates the names for lexc lexica from category (POS) plus delimiter sequences by joining
    the categories and delimiters into a string and using that string to generate an MD5 hash.  Thus the
    category sequence ('Asp', '-', 'V', '-', 'Agr') would imply a root category MD5('Asp-V-Agr') as well
    as the following continuation classes MD5('-V-Agr') MD5('V-Agr') MD5('-Agr') MD5('Agr')

    """
    def pos_sequence_2_lexicon_name(pos_sequence, morpheme_delimiters):
        """Return a foma lexc lexicon name for the tuple of categories and delimiters; output is an MD5 hash."""
        return hashlib.md5(u''.join(pos_sequence).encode('utf8')).hexdigest()

    def get_lexicon_entries_generator(pos_sequence, morphemes, morpheme_delimiters):
        """Return a generator that yields a line for each entry in a lexc LEXICON based on a POS sequence.

        :param tuple pos_sequence: something like ('N', '-', 'Ninf') or ('-', 'Ninf').
        :param dict morphemes: {'N': [(u'chien', u'dog'), (u'chat', u'cat'), ...], 'V': ...}
        :param list morpheme_delimiters: the morpheme delimiters defined in the application settings.
        :yields: lines that compries the entries in a foma lexc LEXICON declaration.

        """
        if len(pos_sequence) == 1:
            next_class = u'#'
        else:
            next_class = pos_sequence_2_lexicon_name(pos_sequence[1:], morpheme_delimiters)
        first_element = pos_sequence[0]
        if first_element in morpheme_delimiters:
            yield u'%s %s;\n' % (first_element, next_class)
        else:
            our_morphemes = morphemes.get(first_element, [])
            for form, gloss in our_morphemes:
                form = h.escape_foma_reserved_symbols(form)
                gloss = h.escape_foma_reserved_symbols(gloss)
                yield u'%s%s%s:%s %s;\n' % (form, h.rare_delimiter, gloss, form, next_class)
        yield u'\n\n'

    # I was declaring all morpheme glosses as multi-character symbols in the lexc foma script but
    # this was causing issues in accuracy as well as efficiency of compilation.  I don't quite know why...
    #glosses = set()
    #for morphemes_list in morphemes.values():
    #    for form, gloss in morphemes_list:
    #        glosses.add(gloss)
    #glosses = map(h.escape_foma_reserved_symbols, glosses)
    #yield u'Multichar_Symbols %s\n' % glosses[0]
    #for gloss in glosses[1:]:
    #    yield u'  %s\n' % gloss
    #yield u'\n\n\n'

    roots = []
    continuation_classes = set()
    for sequence in pos_sequences:
        roots.append(pos_sequence_2_lexicon_name(sequence, morpheme_delimiters))
        for index in range(len(sequence)):
            continuation_classes.add(sequence[index:])
    continuation_classes = sorted(continuation_classes, key=len, reverse=True)
    yield u'LEXICON Root\n\n'
    for root in roots:
        yield '%s ;\n' % root
    yield u'\n\n'
    for continuation_class in continuation_classes:
        yield u'LEXICON %s\n\n' % pos_sequence_2_lexicon_name(continuation_class, morpheme_delimiters)
        for line in get_lexicon_entries_generator(continuation_class, morphemes, morpheme_delimiters):
            yield line

def get_regex_morphology_generator(morphemes, pos_sequences):
    """Return a generator that yields lines of a foma script representing the morphology using standard regular expressions.
    Contrast this with the lexc approach utilized by ``get_lexc_morphology_generator``.

    :param dict morphemes: a dict from category names to lists of (form, gloss) tuples.
    :param list pos_sequences: a sorted list of tuples  whose elements are categories and morpheme delimiters.
    :yields: lines of a regex foma script

    """
    def get_lexicon_generator(morphemes):
        """Return a generator that yields lines of a foma script defining a lexicon.

        :param morphemes: dict from category names to lists of (mb, mg) tuples.
        :yields: unicode object (lines) that comprise a valid foma script defining a lexicon.

        .. note::

            The presence of a form of category N with a morpheme break value of 'chien' and
            a morpheme gloss value of 'dog' will result in the regex defined as 'N' having
            'c h i e n "|dog":0' as one of its disjuncts.  This is a transducer that maps
            'chien|dog' to 'chien', i.e,. '"|dog"' is a multi-character symbol that is mapped
            to the null symbol, i.e., '0'.  Note also that the vertical bar '|' character is 
            not actually used -- the delimiter character is actually that defined in ``utils.rare_delimiter``
            which, by default, is U+2980 'TRIPLE VERTICAL BAR DELIMITER'.

        """
        delimiter =  h.rare_delimiter
        for pos, data in sorted(morphemes.items()):
            foma_regex_name = get_valid_foma_regex_name(pos)
            if foma_regex_name:
                yield u'define %s [\n' % foma_regex_name
                if data:
                    for mb, mg in data[:-1]:
                        yield u'    %s "%s%s":0 |\n' % (
                            u' '.join(map(h.escape_foma_reserved_symbols, list(mb))), delimiter, mg)
                    yield u'    %s "%s%s":0 \n' % (
                        u' '.join(map(h.escape_foma_reserved_symbols, list(data[-1][0]))), delimiter, data[-1][1])
                yield u'];\n\n'

    def get_valid_foma_regex_name(candidate):
        """Return the candidate foma regex name with all reserved symbols removed and suffixed
        by "Cat".  This prevents conflicts between regex names and symbols in regexes.

        """
        name = h.delete_foma_reserved_symbols(candidate)
        if not name:
            return None
        return u'%sCat' % name

    def pos_sequence_2_foma_disjunct(pos_sequence):
        """Return a foma disjunct representing a POS sequence.

        :param tuple pos_sequence: a tuple where the oddly indexed elements are 
            delimiters and the evenly indexed ones are category names.
        :returns: a unicode object representing a foma disjunct, e.g., u'AGR "-" V'

        """
        tmp = []
        for index, element in enumerate(pos_sequence):
            if index % 2 == 0:
                tmp.append(get_valid_foma_regex_name(element))
            else:
                tmp.append('"%s"' % element)
        if None in tmp:
            return None
        return u' '.join(tmp)

    def get_word_formation_rules_generator(pos_sequences):
        """Return a generator that yields lines for a foma script defining morphological rules.

        :param list pos_sequences: tuples containing categories and delimiters
        :yields: unicode objects (lines) that comprise a valid foma script defining morphological rules

        """
        yield u'define morphology (\n'
        foma_disjuncts = filter(None, map(pos_sequence_2_foma_disjunct, pos_sequences))
        if foma_disjuncts:
            for foma_disjunct in foma_disjuncts[:-1]:
                yield u'    (%s) |\n' % foma_disjunct
            yield u'    (%s) \n' % foma_disjuncts[-1]
        yield u');\n\n'

    for line in get_lexicon_generator(morphemes):
        yield line
    yield u'\n\n'
    for line in get_word_formation_rules_generator(pos_sequences):
        yield line

################################################################################
# MORPHEME LANGUAGE MODEL
################################################################################

def write_morpheme_language_model_files(**kwargs):
    """Using the morpheme language model, write the following files to disk:

    - morpheme language model corpus: a corpus of words, one word per line, morphemes space-delimited (parseable by toolkit ngram estimator).
    - morpheme language model in ARPA format -- generated by LM toolkit from corpus file (and vocabulary file).
    - morpheme language model as a Python simplelm.LMTree instance, pickled.

    'script_dir_path': morpheme_language_model_dir_path, 'user_id': session['user'].id,
    'verification_string': verification_string, 'timeout': h.morpheme_language_model_generate_timeout}
    """
    morpheme_language_model = Session.query(model.MorphemeLanguageModel).\
            get(kwargs['morpheme_language_model_id'])
    morpheme_language_model_path = kwargs['morpheme_language_model_path']
    morpheme_delimiters = h.get_morpheme_delimiters()
    language_model_pickle_path = h.get_model_file_path(morpheme_language_model,
            morpheme_language_model_path, file_type='lm_trie')
    pickle_path_mod_time = h.get_modification_time(language_model_pickle_path)
    toolkit_executable = h.language_model_toolkits[morpheme_language_model.toolkit]['executable']
    try:
        language_model_corpus_path = write_language_model_corpus(morpheme_language_model,
                morpheme_language_model_path, morpheme_delimiters)
        if h.command_line_program_installed(toolkit_executable):
            language_model_arpa_path, arpa_written = write_arpa_language_model(morpheme_language_model,
                    language_model_corpus_path, **kwargs)
            if arpa_written:
                arpa2pickle(language_model_arpa_path, language_model_pickle_path)
        if h.get_modification_time(language_model_pickle_path) != pickle_path_mod_time:
            morpheme_language_model.generate_succeeded = True
            morpheme_language_model.generate_message = u'Language model successfully generated.'
        else:
            morpheme_language_model.generate_succeeded = False
            morpheme_language_model.generate_message = u'A new language model pickle file was not written.'
    except Exception, e:
        morpheme_language_model.generate_succeeded = False
        morpheme_language_model.generate_message = u'The attempt to write a language model file to disk raised an error: %s.' % e
    morpheme_language_model.generate_attempt = unicode(uuid4())
    morpheme_language_model.modifier_id = kwargs['user_id']
    morpheme_language_model.datetime_modified = h.now()
    Session.commit()

def write_language_model_corpus(morpheme_language_model, morpheme_language_model_path, morpheme_delimiters):
    """Write a word corpus text file using the LM's corpus where each line is a word whose morphemes (in m|g format) are space-delimited.

    :param instance morpheme_language_model: a morpheme language model object.
    :param str morpheme_language_model_path: absolute path to the directory of the morpheme LM.
    :param list morpheme_delimiters: the morpheme delimiters of the application as saved in the settngs.
    :returns: the path to the LM corpus file just written.
    :side effects: if the LM's corpus contains restricted forms, set the ``restricted`` attribute 
        to ``True``.  This will prevent restricted users from accessing the source files.

    """
    language_model_corpus_path = h.get_model_file_path(morpheme_language_model, morpheme_language_model_path, file_type='lm_corpus')
    splitter = u'[%s]' % ''.join(map(h.esc_RE_meta_chars, morpheme_delimiters))
    corpus = morpheme_language_model.corpus
    forms = corpus.forms
    restricted = False
    with codecs.open(language_model_corpus_path, mode='w', encoding='utf8') as f:
        if corpus.form_search:
            for form in forms:
                if form.syntactic_category_string:
                    if not restricted and "restricted" in [t.name for t in form.tags]:
                        restricted = True
                    for morpheme_word, gloss_word in zip(form.morpheme_break.split(), form.morpheme_gloss.split()):
                        f.write(get_lm_corpus_entry(morpheme_word, gloss_word, splitter))
        else:
            form_references = h.get_form_references(corpus.content)
            forms = dict((f.id, f) for f in forms)
            for id in form_references:
                form = forms[id]
                if form.syntactic_category_string:
                    if not restricted and "restricted" in [t.name for t in form.tags]:
                        restricted = True
                    for morpheme_word, gloss_word in zip(form.morpheme_break.split(), form.morpheme_gloss.split()):
                        f.write(get_lm_corpus_entry(morpheme_word, gloss_word, splitter))
    if restricted:
        morpheme_language_model.restricted = True
    return language_model_corpus_path

def write_arpa_language_model(morpheme_language_model, language_model_corpus_path, **kwargs):
    """Write ``morpheme_language_model.lm`` to disk: this is the ARPA-formatted LM generated by the toolkit from the corpus file.

    :param instance morpheme_language_model: the morpheme language model model object.
    :param str morpheme_language_model_path: the absolute path to the directory holding the LM's files.
    :param str language_model_corpus_path: the absolute path to the corpus file of the LM.
    :returns: the path to the LM ARPA file if generated, else ``None``.

    """
    timeout = kwargs['timeout']
    verification_string = kwargs['verification_string']
    morpheme_language_model_path = kwargs['morpheme_language_model_path']
    language_model_arpa_path = h.get_model_file_path(morpheme_language_model, morpheme_language_model_path, file_type='arpa')
    lm_arpa_mod_time = h.get_modification_time(language_model_arpa_path)
    log_path = h.get_model_file_path(morpheme_language_model, morpheme_language_model_path, file_type='log')
    if morpheme_language_model.toolkit == 'mitlm':
        order = str(morpheme_language_model.order)
        smoothing = morpheme_language_model.smoothing or 'ModKN'
        cmd = ['estimate-ngram', '-o', order, '-s', smoothing,
                '-t', language_model_corpus_path, '-wl', language_model_arpa_path]
        if morpheme_language_model.vocabulary_morphology:
            morphology_path = kwargs['morphology_path']
            vocabulary_path = write_vocabulary(morpheme_language_model, morpheme_language_model_path, morphology_path)
            if vocabulary_path:
                cmd += ['-v', vocabulary_path]
    try:
        command = Command(cmd, log_path)
        returncode, output = command.run(timeout=timeout)
        if (verification_string in output and returncode == 0 and os.path.isfile(language_model_arpa_path) and
        (lm_arpa_mod_time != h.get_modification_time(language_model_arpa_path))):
            return language_model_arpa_path, True
        else:
            return language_model_arpa_path, False
    except Exception:
        return language_model_arpa_path, False

def arpa2pickle(arpa_file_path, pickle_file_path):
    """Load the contents of an ARPA-formatted LM file into a ``simplelm.LMTree`` instance and pickle it.

    :param str arpa_file_path: absolute path to the ARPA-formatted LM file.
    :param str pickle_file_path: absolute path to the .pickle file that will be written.
    :returns: None

    """
    language_model_trie = simplelm.load_arpa(arpa_file_path, 'utf8')
    cPickle.dump(language_model_trie, open(pickle_file_path, 'wb'))

def write_vocabulary(morpheme_language_model, morpheme_language_model_path, morphology_path):
    """Write the lexicon of ``vocabulary_morphology`` to file in the language model's directory and return the path.

    The format of the vocabulary file written is the same as the output of MITLM's
    ``estimate-ngram -t corpus -write-vocab vocab``, i.e., one word/morpheme per line.

    :param instance vocabulary_morphology: a morphology model object.
    :param str morpheme_language_model_path: absolute path the morpheme language model's directory.
    :returns: the path to the newly written vocabulary file or ``None`` if it could not be written.

    """
    vocabulary_morphology = morpheme_language_model.vocabulary_morphology
    vocabulary_path = h.get_model_file_path(morpheme_language_model, morpheme_language_model_path, file_type='vocabulary')
    morphology_lexicon_path = h.get_model_file_path(vocabulary_morphology, morphology_path, file_type='lexicon')
    if not os.path.isfile(morphology_lexicon_path):
        return None
    lexicon = cPickle.load(open(morphology_lexicon_path, 'rb'))
    with codecs.open(vocabulary_path, mode='w', encoding='utf8') as f:
        f.write(u'%s\n' % h.lm_start)    # write <s> as a vocabulary item
        for morpheme_list in lexicon.values():
            for morpheme_form, morpheme_gloss in morpheme_list:
                f.write(u'%s%s%s\n' % (morpheme_form, h.rare_delimiter, morpheme_gloss))
        f.write(u'\n')
    return vocabulary_path

def evaluate_morpheme_language_model(**kwargs):
    """Use the LM toolkit to calculate the perplexity of the LM by dividing its corpus of words into
    training and test sets.
    """
    morpheme_language_model = Session.query(model.MorphemeLanguageModel).\
            get(kwargs['morpheme_language_model_id'])
    toolkit_executable = h.language_model_toolkits[morpheme_language_model.toolkit]['executable']
    kwargs['morpheme_language_model'] = morpheme_language_model
    kwargs['n'] = 5 # number of test/training set pairs to create
    try:
        if h.command_line_program_installed(toolkit_executable):
            perplexity = compute_perplexity(**kwargs)
            if perplexity:
                morpheme_language_model.perplexity = perplexity
                morpheme_language_model.perplexity_computed = True
            else:
                morpheme_language_model.perplexity = None
                morpheme_language_model.perplexity_computed = False
        else:
            morpheme_language_model.perplexity = None
            morpheme_language_model.perplexity_computed = False
    except Exception:
        morpheme_language_model.perplexity = None
        morpheme_language_model.perplexity_computed = False
    morpheme_language_model.perplexity_attempt = unicode(uuid4())
    morpheme_language_model.modifier_id = kwargs['user_id']
    morpheme_language_model.datetime_modified = h.now()
    Session.commit()

def compute_perplexity(**kwargs):
    morpheme_language_model = kwargs['morpheme_language_model']
    morpheme_language_model_path = kwargs['morpheme_language_model_path']
    timeout = kwargs['timeout']
    n = kwargs['n']
    log_path = h.get_model_file_path(morpheme_language_model, morpheme_language_model_path, file_type='log')
    # estimate-ngram -t training_set_path -wl training_set_lm_path -eval-perp test_set_path
    perplexities = []
    temp_paths = []
    morpheme_delimiters = h.get_morpheme_delimiters()
    splitter = u'[%s]' % ''.join(map(h.esc_RE_meta_chars, morpheme_delimiters))
    if morpheme_language_model.toolkit == 'mitlm':
        for i in range(1, n + 1):
            training_set_path, test_set_path, training_set_lm_path = write_training_test_sets(
                morpheme_language_model, morpheme_language_model_path, i, splitter)
            temp_paths += [training_set_path, test_set_path, training_set_lm_path]
            order = str(morpheme_language_model.order)
            smoothing = morpheme_language_model.smoothing or 'ModKN'
            cmd = ['estimate-ngram', '-o', order, '-s', smoothing, '-t', training_set_path,
                   '-wl', training_set_lm_path, '-eval-perp', test_set_path]
            if morpheme_language_model.vocabulary_morphology:
                vocabulary_path = h.get_model_file_path(morpheme_language_model, morpheme_language_model_path, file_type='vocabulary')
                if not os.path.isfile(vocabulary_path):
                    return None
                cmd += ['-v', vocabulary_path]
            try:
                command = Command(cmd, log_path)
                returncode, output = command.run(timeout=timeout)
                if returncode == 0 and os.path.isfile(training_set_lm_path):
                    perplexities.append(extract_perplexity(output))
            except Exception:
                pass
    for path in temp_paths:
        try:
            os.remove(path)
        except Exception:
            pass
    perplexities = filter(None, perplexities)
    if perplexities:
        return sum(perplexities) / len(perplexities)
    else:
        return None

def extract_perplexity(output):
    """Extract the perplexity value from the output of MITLM
    """
    try:
        last_line = output.splitlines()[-1]
        return float(last_line.split()[-1])
    except Exception:
        return None

def get_lm_corpus_entry(morpheme_word, gloss_word, splitter):
    """Return a string of morphemes space-delimited in m|g format where "|" is ``h.rare_delimiter``.
    """
    return '%s\n' % u' '.join('%s%s%s' % (morpheme, h.rare_delimiter, gloss) for morpheme, gloss in
        zip(re.split(splitter, morpheme_word), re.split(splitter, gloss_word)))

def write_training_test_sets(morpheme_language_model, morpheme_language_model_path, i, splitter):
    template_path = h.get_model_file_path(morpheme_language_model, morpheme_language_model_path)
    test_set_path = '%s_test_%s.txt' % (template_path, i)
    training_set_path = '%s_training_%s.txt' % (template_path, i)
    training_set_lm_path = '%s_training_%s.lm' % (template_path, i)
    corpus = morpheme_language_model.corpus
    forms = corpus.forms
    population = range(1, 11)
    test_index = random.choice(population)
    with codecs.open(training_set_path, mode='w', encoding='utf8') as f_training:
        with codecs.open(test_set_path, mode='w', encoding='utf8') as f_test:
            if corpus.form_search:
                for form in forms:
                    if form.syntactic_category_string:
                        for morpheme_word, gloss_word in zip(form.morpheme_break.split(), form.morpheme_gloss.split()):
                            r = random.choice(population)
                            if r == test_index:
                                f_test.write(get_lm_corpus_entry(morpheme_word, gloss_word, splitter))
                            else:
                                f_training.write(get_lm_corpus_entry(morpheme_word, gloss_word, splitter))
            else:
                form_references = h.get_form_references(corpus.content)
                forms = dict((f.id, f) for f in forms)
                for id in form_references:
                    form = forms[id]
                    if form.syntactic_category_string:
                        for morpheme_word, gloss_word in zip(form.morpheme_break.split(), form.morpheme_gloss.split()):
                            r = random.choice(population)
                            if r == test_index:
                                f_test.write(get_lm_corpus_entry(morpheme_word, gloss_word, splitter))
                            else:
                                f_training.write(get_lm_corpus_entry(morpheme_word, gloss_word, splitter))
    return training_set_path, test_set_path, training_set_lm_path
