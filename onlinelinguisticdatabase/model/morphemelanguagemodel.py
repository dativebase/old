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

"""Morpheme language model model"""

import codecs
import os
import cPickle
import random
from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime, Boolean, Float
from sqlalchemy.orm import relation
from onlinelinguisticdatabase.model.meta import Base, now
from onlinelinguisticdatabase.lib.parser import LanguageModel
import logging

log = logging.getLogger(__name__)

class MorphemeLanguageModel(LanguageModel, Base):
    """The OLD currently uses the MITLM toolkit to build its language models. 
    Support for CMU-Cambridge, SRILM, KenLM, etc. may be forthcoming...

    """

    __tablename__ = 'morphemelanguagemodel'

    def __repr__(self):
        return '<MorphemeLanguageModel (%s)>' % self.id

    id = Column(Integer, Sequence('morphemelanguagemodel_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    corpus_id = Column(Integer, ForeignKey('corpus.id', ondelete='SET NULL'))
    corpus = relation('Corpus') # whence we extract the morpheme sequences and their counts
    enterer_id = Column(Integer, ForeignKey('user.id', ondelete='SET NULL'))
    enterer = relation('User', primaryjoin='MorphemeLanguageModel.enterer_id==User.id')
    modifier_id = Column(Integer, ForeignKey('user.id', ondelete='SET NULL'))
    modifier = relation('User', primaryjoin='MorphemeLanguageModel.modifier_id==User.id')
    datetime_entered = Column(DateTime)
    datetime_modified = Column(DateTime, default=now)
    generate_succeeded = Column(Boolean, default=False)
    generate_message = Column(Unicode(255))
    generate_attempt = Column(Unicode(36)) # a UUID
    perplexity = Column(Float, default=0.0)
    perplexity_attempt = Column(Unicode(36)) # a UUID
    perplexity_computed = Column(Boolean, default=False)
    toolkit = Column(Unicode(10))
    order = Column(Integer)
    smoothing = Column(Unicode(30))
    vocabulary_morphology_id = Column(Integer, ForeignKey('morphology.id', ondelete='SET NULL'))
    vocabulary_morphology = relation('Morphology') # if specified, LM will use the lexicon of the morphology as the fixed vocabulary
    restricted = Column(Boolean, default=False)
    categorial = Column(Boolean, default=False) # if True, the model will be built over sequences of categories, not morphemes
    morpheme_delimiters = Column(Unicode(255))

    # These incidental attributes are initialized by the constructor.
    parent_directory = Column(Unicode(255))
    rare_delimiter = Column(Unicode(10))
    start_symbol = Column(Unicode(10))
    end_symbol = Column(Unicode(10))

    def get_dict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'name': self.name,
            'corpus': self.get_mini_dict_for(self.corpus),
            'description': self.description,
            'enterer': self.get_mini_user_dict(self.enterer),
            'modifier': self.get_mini_user_dict(self.modifier),
            'datetime_entered': self.datetime_entered,
            'datetime_modified': self.datetime_modified,
            'generate_succeeded': self.generate_succeeded,
            'generate_message': self.generate_message,
            'generate_attempt': self.generate_attempt,
            'perplexity': self.perplexity,
            'perplexity_attempt': self.perplexity_attempt,
            'perplexity_computed': self.perplexity_computed,
            'toolkit': self.toolkit,
            'order': self.order,
            'smoothing': self.smoothing,
            'vocabulary_morphology': self.get_mini_dict_for(self.vocabulary_morphology),
            'restricted': self.restricted,
            'categorial': self.categorial
        }

    def write_corpus(self):
        """Write a word corpus text file using the LM's corpus where each line is a word.

        If the LM is categorial, the word is represented as a space-delimited list of category names
        corresponding to the categories of the morphemes of the word; otherwise, it is represented as 
        a space-delimited list of morphemes in form|gloss|category format.

        :returns: the path to the LM corpus file just written.
        :side effects: if the LM's corpus contains restricted forms, set the ``restricted`` attribute 
            to ``True``.  This will prevent restricted users from accessing the source files.

        """
        corpus_path = self.get_file_path('corpus')
        corpus = self.corpus
        forms = corpus.forms
        restricted = False
        with codecs.open(corpus_path, mode='w', encoding='utf8') as f:
            if corpus.form_search:
                for form in forms:
                    if form.syntactic_category_string:
                        if not restricted and "restricted" in [t.name for t in form.tags]:
                            restricted = True
                        if self.categorial:
                            for category_word in form.syntactic_category_string.split():
                                f.write(self._get_categorial_corpus_entry(category_word))
                        else:
                            for morpheme_word, gloss_word, category_word in zip(form.morpheme_break.split(),
                                form.morpheme_gloss.split(), form.syntactic_category_string.split()):
                                f.write(self._get_morphemic_corpus_entry(
                                    morpheme_word, gloss_word, category_word))
            else:
                form_references = corpus.get_form_references(corpus.content)
                forms = dict((f.id, f) for f in forms)
                for id in form_references:
                    form = forms[id]
                    if form.syntactic_category_string:
                        if not restricted and "restricted" in [t.name for t in form.tags]:
                            restricted = True
                        if self.categorial:
                            for category_word in form.syntactic_category_string.split():
                                f.write(self._get_categorial_corpus_entry(category_word))
                        else:
                            for morpheme_word, gloss_word, category_word in zip(form.morpheme_break.split(),
                                form.morpheme_gloss.split(), form.syntactic_category_string.split()):
                                f.write(self._get_morphemic_corpus_entry(
                                    morpheme_word, gloss_word, category_word))
        if restricted:
            self.restricted = True
        return corpus_path

    def write_vocabulary(self):
        """Write the vocabulary file, if appropriate.

        If the LM has a vocabulary morphology, use its lexicon to write a vocabulary file and
        return the path.  The format of the vocabulary file written is the same as the output
        of MITLM's ``estimate-ngram -t corpus -write-vocab vocab``, i.e., one word/morpheme per line.

        :returns: the path to the newly written vocabulary file or ``None`` if it could not be written.

        """

        vocabulary_morphology = self.vocabulary_morphology
        if not vocabulary_morphology:
            return
        vocabulary_path = self.get_file_path('vocabulary')
        lexicon_path = vocabulary_morphology.get_file_path('lexicon')
        if not os.path.isfile(lexicon_path):
            return
        # A pickled morphology lexicon is a dict with categories as keys and lists of
        # (morpheme_form, morpheme_gloss) 2-tuples as values.
        lexicon = cPickle.load(open(lexicon_path, 'rb'))
        with codecs.open(vocabulary_path, mode='w', encoding='utf8') as f:
            f.write(u'%s\n' % self.start_symbol)    # write <s> as a vocabulary item
            if self.categorial:
                for category in lexicon:
                    f.write(u'%s\n' % category)
            else:
                for category, morpheme_list in lexicon.iteritems():
                    for morpheme_form, morpheme_gloss in morpheme_list:
                        f.write(u'%s\n' % self.rare_delimiter.join(
                            [morpheme_form, morpheme_gloss, category]))
            f.write(u'\n')
        return vocabulary_path

    def compute_perplexity(self, timeout, iterations):
        """Compute the perplexity of a the language model.

        The method used is to create ``iterations`` training/test set pairs, compute the perplexity
        of each test set based on an LM generated from its training set and return the average
        perplexity value.

        """

        perplexities = []
        temp_paths = [] # will hold the paths to all the temporary files that we delete below.
        if self.toolkit == 'mitlm':
            for index in range(1, iterations + 1):
                training_set_path, test_set_path, training_set_lm_path = \
                    self.write_training_test_sets(index)
                temp_paths += [training_set_path, test_set_path, training_set_lm_path]
                order = str(self.order)
                smoothing = self.smoothing or 'ModKN'
                cmd = [self.executable, '-o', order, '-s', smoothing, '-t', training_set_path,
                    '-wl', training_set_lm_path, '-eval-perp', test_set_path]
                if self.vocabulary_morphology:
                    vocabulary_path = self.get_file_path('vocabulary')
                    if not os.path.isfile(vocabulary_path):
                        return None
                    cmd += ['-v', vocabulary_path]
                try:
                    returncode, output = self.run(cmd, timeout)
                    if returncode == 0 and os.path.isfile(training_set_lm_path):
                        perplexities.append(self.extract_perplexity(output))
                except Exception:
                    pass
        else:
            return None
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

    def extract_perplexity(self, output):
        """Extract the perplexity value from the output of MITLM.
        """
        try:
            last_line = output.splitlines()[-1]
            return float(last_line.split()[-1])
        except Exception:
            return None

    def _get_morphemic_corpus_entry(self, morpheme_word, gloss_word, category_word):
        """Return a string of morphemes, space-delimited in m|g|c format where "|" is ``self.rare_delimiter``.

        """
        return '%s\n' % u' '.join(self.rare_delimiter.join([morpheme, gloss, category])
            for morpheme, gloss, category in
            zip(self.morpheme_only_splitter(morpheme_word),
                self.morpheme_only_splitter(gloss_word),
                self.morpheme_only_splitter(category_word)))

    def _get_categorial_corpus_entry(self, category_word):
        """Return a string of morpheme category names, space-delimited.

        """
        return u'%s\n' % u' '.join(self.morpheme_only_splitter(category_word))

    def write_training_test_sets(self, index):
        """Divide the words implicit in the LM's corpus into randomly sampled training and test sets and write them to disk with the suffix ``i``.
        Use the toolkit of the morpheme language model to generate an ARPA-formatted LM for the training set.

        :param instance morpheme_language_model: a LM model object.
        :param str morpheme_language_model_path: absolute path to the LM's directory.
        :param int i: index used in naming the test and training sets.
        :returns: a triple of strings: the absolute paths to the training and test sets and
        the path to the training set's ARPA-formatted LM.

        """
        directory = self.directory
        test_set_path = '%s_test_%s.txt' % (directory, index)
        training_set_path = '%s_training_%s.txt' % (directory, index)
        training_set_lm_path = '%s_training_%s.lm' % (directory, index)
        corpus = self.corpus
        forms = corpus.forms
        population = range(1, 11)
        test_index = random.choice(population)
        with codecs.open(training_set_path, mode='w', encoding='utf8') as f_training:
            with codecs.open(test_set_path, mode='w', encoding='utf8') as f_test:
                if corpus.form_search:
                    for form in forms:
                        if form.syntactic_category_string:
                            if self.categorial:
                                for category_word in form.syntactic_category_string.split():
                                    r = random.choice(population)
                                    if r == test_index:
                                        f_test.write(self._get_categorial_corpus_entry(
                                            category_word))
                                    else:
                                        f_training.write(self._get_categorial_corpus_entry(
                                            category_word))
                            else:
                                for morpheme_word, gloss_word, category_word in zip(
                                    form.morpheme_break.split(),
                                    form.morpheme_gloss.split(),
                                    form.syntactic_category_string.split()):
                                    r = random.choice(population)
                                    if r == test_index:
                                        f_test.write(self._get_morphemic_corpus_entry(
                                            morpheme_word, gloss_word, category_word))
                                    else:
                                        f_training.write(self._get_morphemic_corpus_entry(
                                            morpheme_word, gloss_word, category_word))
                else:
                    form_references = corpus.get_form_references(corpus.content)
                    forms = dict((f.id, f) for f in forms)
                    for id in form_references:
                        form = forms[id]
                        if form.syntactic_category_string:
                            if self.categorial:
                                for category_word in form.syntactic_category_string.split():
                                    r = random.choice(population)
                                    if r == test_index:
                                        f_test.write(self._get_categorial_corpus_entry(
                                            category_word))
                                    else:
                                        f_training.write(self._get_categorial_corpus_entry(
                                            category_word))
                            else:
                                for morpheme_word, gloss_word, category_word in zip(
                                    form.morpheme_break.split(),
                                    form.morpheme_gloss.split(),
                                    form.syntactic_category_string.split()):
                                    r = random.choice(population)
                                    if r == test_index:
                                        f_test.write(self._get_morphemic_corpus_entry(
                                            morpheme_word, gloss_word, category_word))
                                    else:
                                        f_training.write(self._get_morphemic_corpus_entry(
                                            morpheme_word, gloss_word, category_word))
        return training_set_path, test_set_path, training_set_lm_path

