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

"""MorphologyBackup model

Used to save morphology data that has been updated or deleted.  This is a
non-relational table, because keeping a copy of every single change relationally
seemed like more trouble than it's worth.
"""

from sqlalchemy import Column, Sequence
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime, Boolean
from onlinelinguisticdatabase.model.meta import Base, now
import simplejson as json
import logging

log = logging.getLogger(__name__)

class MorphologyBackup(Base):
    """Class for creating OLD morphologyBackup models.

    The vivify method takes a morphology and a user object as input and populates
    a number of morphology-like attributes, converting relational attributes to
    JSON objects.

    """

    __tablename__ = "morphologybackup"
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<MorphologyBackup (%s)>" % self.id

    id = Column(Integer, Sequence('morphologybackup_seq_id', optional=True), primary_key=True)
    morphology_id = Column(Integer)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    script_type = Column(Unicode(5))
    lexiconCorpus = Column(UnicodeText)
    rulesCorpus = Column(UnicodeText)
    enterer = Column(UnicodeText)
    modifier = Column(UnicodeText)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    compileSucceeded = Column(Boolean, default=False)
    compileMessage = Column(Unicode(255))
    compile_attempt = Column(Unicode(36))
    generate_attempt = Column(Unicode(36))
    extract_morphemes_from_rules_corpus = Column(Boolean, default=False)

    def vivify(self, morphologyDict):
        """The vivify method gives life to a morphologyBackup by specifying its
        attributes using the to-be-backed-up morphology (morphologyDict) and the
        modifier (current user).  The relational attributes of the
        to-be-backed-up morphology are converted into (truncated) JSON objects.

        """
        self.UUID = morphologyDict['UUID']
        self.morphology_id = morphologyDict['id']
        self.name = morphologyDict['name']
        self.description = morphologyDict['description']
        self.script_type = morphologyDict['script_type']
        self.rulesCorpus = unicode(json.dumps(morphologyDict['rulesCorpus']))
        self.lexiconCorpus = unicode(json.dumps(morphologyDict['lexiconCorpus']))
        self.enterer = unicode(json.dumps(morphologyDict['enterer']))
        self.modifier = unicode(json.dumps(morphologyDict['modifier']))
        self.datetimeEntered = morphologyDict['datetimeEntered']
        self.datetimeModified = morphologyDict['datetimeModified']
        self.compileSucceeded = morphologyDict['compileSucceeded']
        self.compileMessage = morphologyDict['compileMessage']
        self.compile_attempt = morphologyDict['compile_attempt']
        self.generate_attempt = morphologyDict['generate_attempt']
        self.extract_morphemes_from_rules_corpus = morphologyDict['extract_morphemes_from_rules_corpus']

    def getDict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'morphology_id': self.morphology_id,
            'name': self.name,
            'description': self.description,
            'script_type': self.script_type,
            'rulesCorpus': self.jsonLoads(self.rulesCorpus),
            'lexiconCorpus': self.jsonLoads(self.lexiconCorpus),
            'enterer': self.jsonLoads(self.enterer),
            'modifier': self.jsonLoads(self.modifier),
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'compileSucceeded': self.compileSucceeded,
            'compileMessage': self.compileMessage,
            'compile_attempt': self.compile_attempt,
            'generate_attempt': self.generate_attempt,
            'extract_morphemes_from_rules_corpus': self.extract_morphemes_from_rules_corpus
        }
