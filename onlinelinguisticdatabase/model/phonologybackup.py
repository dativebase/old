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

"""PhonologyBackup model

Used to save phonology data that has been updated or deleted.  This is a
non-relational table, because keeping a copy of every single change relationally
seemed like more trouble than it's worth.
"""

from sqlalchemy import Column, Sequence
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime, Boolean
from onlinelinguisticdatabase.model.meta import Base, now
import simplejson as json

class PhonologyBackup(Base):
    """Class for creating OLD phonologyBackup models.

    The vivify method takes a phonology and a user object as input and populates
    a number of phonology-like attributes, converting relational attributes to
    JSON objects.

    """

    __tablename__ = "phonologybackup"
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<PhonologyBackup (%s)>" % self.id

    id = Column(Integer, Sequence('phonologybackup_seq_id', optional=True), primary_key=True)
    phonology_id = Column(Integer)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    script = Column(UnicodeText)
    enterer = Column(UnicodeText)
    modifier = Column(UnicodeText)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    compileSucceeded = Column(Boolean, default=False)
    compileMessage = Column(Unicode(255))
    compile_attempt = Column(Unicode(36))

    def vivify(self, phonologyDict):
        """The vivify method gives life to a phonologyBackup by specifying its
        attributes using the to-be-backed-up phonology (phonologyDict) and the
        modifier (current user).  The relational attributes of the
        to-be-backed-up phonology are converted into (truncated) JSON objects.

        """

        self.UUID = phonologyDict['UUID']
        self.phonology_id = phonologyDict['id']
        self.name = phonologyDict['name']
        self.description = phonologyDict['description']
        self.script = phonologyDict['script']
        self.enterer = unicode(json.dumps(phonologyDict['enterer']))
        self.modifier = unicode(json.dumps(phonologyDict['modifier']))
        self.datetimeEntered = phonologyDict['datetimeEntered']
        self.datetimeModified = phonologyDict['datetimeModified']
        self.compileSucceeded = phonologyDict['compileSucceeded']
        self.compileMessage = phonologyDict['compileMessage']
        self.compile_attempt = phonologyDict['compile_attempt']

    def getDict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'phonology_id': self.phonology_id,
            'name': self.name,
            'description': self.description,
            'script': self.script,
            'enterer': self.jsonLoads(self.enterer),
            'modifier': self.jsonLoads(self.modifier),
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'compileSucceeded': self.compileSucceeded,
            'compileMessage': self.compileMessage,
            'compile_attempt': self.compile_attempt
        }
