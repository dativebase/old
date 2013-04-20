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

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Boolean
from sqlalchemy.orm import relation, backref
from onlinelinguisticdatabase.model.meta import Base, now

class Morphology(Base):

    __tablename__ = 'morphology'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Morphology (%s)>' % self.id

    id = Column(Integer, Sequence('morphology_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    script = Column(UnicodeText)
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
    datetimeCompiled = Column(DateTime)
    compileSucceeded = Column(Boolean, default=False)
    compileMessage = Column(Unicode(255))

    def getDict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'name': self.name,
            'lexiconCorpus': self.lexiconCorpus.getMiniDict(),
            'rulesCorpus': self.rulesCorpus.getMiniDict(),
            'script': self.script,
            'description': self.description,
            'enterer': self.getMiniUserDict(self.enterer),
            'modifier': self.getMiniUserDict(self.modifier),
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'datetimeCompiled': self.datetimeCompiled,
            'compileSucceeded': self.compileSucceeded,
            'compileMessage': self.compileMessage
        }
