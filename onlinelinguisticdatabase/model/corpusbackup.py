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

"""Corpus backup model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from onlinelinguisticdatabase.model.meta import Base, now

class CorpusBackup(Base):

    __tablename__ = 'corpusbackup'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<CorpusBackup (%s)>" % self.id

    id = Column(Integer, Sequence('corpusbackup_seq_id', optional=True), primary_key=True)
    corpus_id = Column(Integer)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    type = Column(Unicode(255))
    description = Column(UnicodeText)
    content = Column(UnicodeText)
    enterer = Column(UnicodeText)
    modifier = Column(UnicodeText)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    tags = Column(UnicodeText)
    forms = Column(UnicodeText)

    def vivify(self, corpusDict):
        """The vivify method gives life to a corpusBackup by specifying its
        attributes using the to-be-backed-up corpus as represented in
        ``corpusDict``.  The relational attributes of the backup are converted
        to (truncated) JSON objects.

        """

        self.UUID = corpusDict['UUID']
        self.corpus_id = corpusDict['id']
        self.name = corpusDict['name']
        self.type = corpusDict['type']
        self.description = corpusDict['description']
        self.content = corpusDict['content']
        self.enterer = unicode(json.dumps(corpusDict['enterer']))
        self.modifier = unicode(json.dumps(corpusDict['modifier']))
        self.datetimeEntered = corpusDict['datetimeEntered']
        self.datetimeModified = corpusDict['datetimeModified']
        self.forms = unicode(json.dumps([f['id'] for f in corpusDict['forms']]))
        self.tags = unicode(json.dumps(corpusDict['tags']))

    def getDict(self):
        """Return a Python dictionary representation of the Corpus.  This
        facilitates JSON-stringification, cf. utils.JSONOLDEncoder.  Relational
        data are truncated, e.g., corpusDict['enterer'] is a dict with keys
        for 'id', 'firstName' and 'lastName' (cf. getMiniUserDict) and
        lacks keys for other attributes such as 'username',
        'personalPageContent', etc.
        """

        return {
            'id': self.id,
            'corpus_id': self.corpus_id,
            'UUID': self.UUID,
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'content': self.content,
            'enterer': self.jsonLoads(self.enterer),
            'modifier': self.jsonLoads(self.modifier),
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'tags': self.jsonLoads(self.tags),
            'forms': self.jsonLoads(self.forms)
        }
