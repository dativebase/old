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
    lexiconCorpus_id = Column(Integer, ForeignKey('corpus.id'))
    lexiconCorpus = relation('Corpus', primaryjoin='Morphology.lexiconCorpus_id==Corpus.id')
    rulesCorpus_id = Column(Integer, ForeignKey('corpus.id'))
    rulesCorpus = relation('Corpus', primaryjoin='Morphology.rulesCorpus_id==Corpus.id')
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='Morphology.enterer_id==User.id')
    modifier_id = Column(Integer, ForeignKey('user.id'))
    modifier = relation('User', primaryjoin='Morphology.modifier_id==User.id')
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    compileSucceeded = Column(Boolean, default=False)
    compileMessage = Column(Unicode(255))
    compile_attempt = Column(Unicode(36)) # a UUID
    generate_attempt = Column(Unicode(36)) # a UUID
    extract_morphemes_from_rules_corpus = Column(Boolean, default=False)
    rules = Column(UnicodeText) # word formation rules (i.e., strings of categories and delimiters) separated by spaces

    def getDict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'name': self.name,
            'lexiconCorpus': self.getMiniDictFor(self.lexiconCorpus),
            'rulesCorpus': self.getMiniDictFor(self.rulesCorpus),
            'script_type': self.script_type,
            'description': self.description,
            'enterer': self.getMiniUserDict(self.enterer),
            'modifier': self.getMiniUserDict(self.modifier),
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'compileSucceeded': self.compileSucceeded,
            'compileMessage': self.compileMessage,
            'compile_attempt': self.compile_attempt,
            'generate_attempt': self.generate_attempt,
            'extract_morphemes_from_rules_corpus': self.extract_morphemes_from_rules_corpus,
            'rules': self.rules
        }
