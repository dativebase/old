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

"""Foma worker thread and queue for the OLD.

The the foma worker compiles foma FST phonology, morphology (and morphophonology) scripts 
in a separate thread from that processing the request thereby permitting an immediate 
response to the user.

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
from subprocess import Popen, PIPE
from signal import SIGKILL

log = logging.getLogger(__name__)

foma_worker_q = Queue.Queue()

class FomaWorkerThread(threading.Thread):
    """Define the foma worker."""
    def run(self):
        while True:
            msg = foma_worker_q.get()
            try:
                globals()[msg.get('func')](**msg.get('args'))
            except Exception, e:
                log.warn('Unable to process in worker thread: %s' % e)
            foma_worker_q.task_done()

def start_foma_worker():
    """Called in :mod:`onlinelinguisticdatabase.config.environment.py`."""
    foma_worker = FomaWorkerThread()
    foma_worker.setDaemon(True)
    foma_worker.start()


################################################################################
# Foma Compile Functions
################################################################################

def get_file_path(model_object, script_dir_path, file_type='script'):
    """Return the path to a foma-based model's file of the given type.

    :param model_object: a phonology or morphology model object.
    :param str script_dir_path: the absolute path to the directory that houses the foma 
        script of the phonology or morphology
    :param str file_type: one of 'script', 'binary', 'compiler' or 'log'.
    :returns: an absolute path to the file of the supplied type for the model object given.

    """
    ext_map = {
        'script': 'script',
        'binary': 'foma',
        'compiler': 'sh',
        'log': 'log',
        'lexicon': 'pickle'
    }
    return os.path.join(script_dir_path,
                '%s_%d.%s' % (model_object.__tablename__, model_object.id, ext_map.get(file_type, 'script')))

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

def compile_phonology_script(**kwargs):
    """Compile the foma script of a phonology and save it to the db with values that indicating compilation success."""
    phonology_id = kwargs['phonology_id']
    phonology = Session.query(model.Phonology).get(phonology_id)
    kwargs['model_object'] = phonology
    phonology = compile_foma_script(**kwargs)
    phonology.datetime_modified = h.now()
    phonology.modifier_id = kwargs['user_id']
    phonology.compile_attempt = unicode(uuid4())
    Session.commit()

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
    compiler_path = kwargs.get('compiler_path', get_file_path(model_object, script_dir_path, 'compiler'))
    binary_path = kwargs.get('binary_path', get_file_path(model_object, script_dir_path, 'binary'))
    log_path = kwargs.get('log_path', get_file_path(model_object, script_dir_path, 'log'))
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
        'script_path': get_file_path(morphology, script_dir_path, 'script'),
        'binary_path': get_file_path(morphology, script_dir_path, 'binary'),
        'compiler_path': get_file_path(morphology, script_dir_path, 'compiler'),
        'log_path': get_file_path(morphology, script_dir_path, 'log'),
        'pos_sequences': rules,
        'morphemes': lexicon,
        'morpheme_delimiters': morpheme_delimiters
    })
    write_morphology_script_to_disk(**kwargs)
    morphology.rules = u' '.join(map(u''.join, rules))
    # pickle the lexicon dict
    lexicon_path = get_file_path(morphology, script_dir_path, 'lexicon')
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

    def extract_word_pos_sequences(form, morpheme_splitter, unknown_category, morphology):
        """Return the unique word-based pos sequences, as well as the morphemes, implicit in the form.

        :param form: a form model object
        :param morpheme_splitter: callable that splits a strings into its morphemes and delimiters
        :param str unknown_category: the string used in syntactic category strings when a morpheme-gloss pair is unknown
        :param morphology: the morphology model object -- needed because its extract_morphemes_from_rules_corpus
            attribute determines whether we return a list of morphemes.
        :returns: 2-tuple: (set of pos/delimiter sequences, list of morphemes as (pos, (mb, mg)) tuples).

        """
        if not form.syntactic_category_string:
            return None, None
        pos_sequences = set()
        morphemes = []
        sc_words = form.syntactic_category_string.split()
        mb_words = form.morpheme_break.split()
        mg_words = form.morpheme_gloss.split()
        for sc_word, mb_word, mg_word in zip(sc_words, mb_words, mg_words):
            pos_sequence = tuple(morpheme_splitter(sc_word))
            if unknown_category not in pos_sequence:
                pos_sequences.add(pos_sequence)
                if morphology.extract_morphemes_from_rules_corpus:
                    morpheme_sequence = morpheme_splitter(mb_word)[::2]
                    gloss_sequence = morpheme_splitter(mg_word)[::2]
                    for pos, morpheme, gloss in zip(pos_sequence[::2], morpheme_sequence, gloss_sequence):
                        morphemes.append((pos, (morpheme, gloss)))
        return pos_sequences, morphemes

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
    morpheme_splitter = lambda x: [x] # default, word is morpheme
    if morpheme_delimiters:
        morpheme_splitter = re.compile(u'([%s])' % ''.join([h.esc_RE_meta_chars(d) for d in morpheme_delimiters])).split
    # Get the unique morphemes from the lexicon corpus
    morphemes = {}
    if (morphology.lexicon_corpus and
        morphology.lexicon_corpus.id != morphology.rules_corpus.id):
        for form in morphology.lexicon_corpus.forms:
            new_morphemes = extract_morphemes_from_form(form, morpheme_splitter, unknown_category)
            for pos, data in new_morphemes:
                morphemes.setdefault(pos, set()).add(data)
    # Get the pos strings (and morphemes) from the words in the rules corpus
    pos_sequences = set()
    for form in morphology.rules_corpus.forms:
        new_pos_sequences, new_morphemes = extract_word_pos_sequences(form, morpheme_splitter, unknown_category, morphology)
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

    glosses = set()
    for morphemes_list in morphemes.values():
        for form, gloss in morphemes_list:
            glosses.add(gloss)
    glosses = map(h.escape_foma_reserved_symbols, glosses)
    yield u'Multichar_Symbols %s\n' % glosses[0]
    for gloss in glosses[1:]:
        yield u'  %s\n' % gloss
    yield u'\n\n\n'
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

