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

"""Morphology model"""

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime, Boolean
from sqlalchemy.orm import relation
from onlinelinguisticdatabase.model.meta import Base, now
import simplejson as json

class Morphology(Base):

    __tablename__ = 'morphology'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Morphology (%s)>' % self.id

    id = Column(Integer, Sequence('morphology_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    script_type = Column(Unicode(5))
    lexicon_corpus_id = Column(Integer, ForeignKey('corpus.id'))
    lexicon_corpus = relation('Corpus', primaryjoin='Morphology.lexicon_corpus_id==Corpus.id')
    rules_corpus_id = Column(Integer, ForeignKey('corpus.id'))
    rules_corpus = relation('Corpus', primaryjoin='Morphology.rules_corpus_id==Corpus.id')
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='Morphology.enterer_id==User.id')
    modifier_id = Column(Integer, ForeignKey('user.id'))
    modifier = relation('User', primaryjoin='Morphology.modifier_id==User.id')
    datetime_entered = Column(DateTime)
    datetime_modified = Column(DateTime, default=now)
    compile_succeeded = Column(Boolean, default=False)
    compile_message = Column(Unicode(255))
    compile_attempt = Column(Unicode(36)) # a UUID
    generate_attempt = Column(Unicode(36)) # a UUID
    extract_morphemes_from_rules_corpus = Column(Boolean, default=False)
    rules_generated = Column(UnicodeText) # word formation rules (i.e., strings of categories and delimiters) separated by spaces -- system-generated value
    rules = Column(UnicodeText) # word formation rules (i.e., strings of categories and delimiters) separated by spaces -- user-generated value
    rich_morphemes = Column(Boolean, default=False) # if True, m=<f|g|c>, else m=f

    def get_dict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'name': self.name,
            'lexicon_corpus': self.get_mini_dict_for(self.lexicon_corpus),
            'rules_corpus': self.get_mini_dict_for(self.rules_corpus),
            'script_type': self.script_type,
            'description': self.description,
            'enterer': self.get_mini_user_dict(self.enterer),
            'modifier': self.get_mini_user_dict(self.modifier),
            'datetime_entered': self.datetime_entered,
            'datetime_modified': self.datetime_modified,
            'compile_succeeded': self.compile_succeeded,
            'compile_message': self.compile_message,
            'compile_attempt': self.compile_attempt,
            'generate_attempt': self.generate_attempt,
            'extract_morphemes_from_rules_corpus': self.extract_morphemes_from_rules_corpus,
            'rules': self.rules,
            'rules_generated': self.rules_generated,
            'rich_morphemes': self.rich_morphemes
        }
