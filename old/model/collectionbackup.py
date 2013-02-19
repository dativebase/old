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

"""CollectionBackup model

Used to save Collection data that has been updated or deleted.  This is a
non-relational table, because keeping a copy of every single change relationally
seemed like more trouble than it's worth.
"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now
import simplejson as json
import datetime

class CollectionBackup(Base):

    __tablename__ = "collectionbackup"
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<CollectionBackup (%s)>" % self.id

    id = Column(Integer, Sequence('collectionbackup_seq_id', optional=True), primary_key=True)
    collection_id = Column(Integer)
    UUID = Column(Unicode(36))
    title = Column(Unicode(255))
    type = Column(Unicode(255))
    url = Column(Unicode(255))
    description = Column(UnicodeText)
    markupLanguage = Column(Unicode(100))
    contents = Column(UnicodeText)
    html = Column(UnicodeText)
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    speaker = Column(UnicodeText)
    source = Column(UnicodeText)
    elicitor = Column(UnicodeText)
    enterer = Column(UnicodeText)
    backuper = Column(UnicodeText)
    tags = Column(UnicodeText)
    files = Column(UnicodeText)
    forms = Column(UnicodeText)

    def vivify(self, collectionDict, backuper, datetimeModified=None):
        """The vivify method gives life to CollectionBackup by specifying its
        attributes using the to-be-backed-up collection (collectionDict) and the
        backuper (current user).  The relational attributes of the
        to-be-backed-up collection are converted into (truncated) JSON objects.
        """

        self.collection_id = collectionDict['id']
        self.UUID = collectionDict['UUID']
        self.title = collectionDict['title']
        self.type = collectionDict['type']
        self.url = collectionDict['url']
        self.description = collectionDict['description']
        self.markupLanguage = collectionDict['markupLanguage']
        self.contents = collectionDict['contents']
        self.html = collectionDict['html']
        self.dateElicited = collectionDict['dateElicited']
        self.datetimeEntered = collectionDict['datetimeEntered']
        if datetimeModified:
            self.datetimeModified = datetimeModified
        else:
            self.datetimeModified = datetime.datetime.utcnow()
        self.source = unicode(json.dumps(collectionDict['source']))
        self.speaker = unicode(json.dumps(collectionDict['speaker']))
        self.elicitor = unicode(json.dumps(collectionDict['elicitor']))
        self.enterer = unicode(json.dumps(collectionDict['enterer']))
        self.backuper = unicode(json.dumps(self.getMiniUserDict(backuper)))
        self.tags = unicode(json.dumps(collectionDict['tags']))
        self.files = unicode(json.dumps(collectionDict['files']))
        self.forms = unicode(json.dumps([f['id'] for f in collectionDict['forms']]))

    def getDict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'collection_id': self.collection_id,
            'title': self.title,
            'type': self.type,
            'url': self.url,
            'description': self.description,
            'markupLanguage': self.markupLanguage,
            'contents': self.contents,
            'html': self.html,
            'dateElicited': self.dateElicited,
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'speaker': self.jsonLoads(self.speaker),
            'source': self.jsonLoads(self.source),
            'elicitor': self.jsonLoads(self.elicitor),
            'enterer': self.jsonLoads(self.enterer),
            'backuper': self.jsonLoads(self.backuper),
            'tags': self.jsonLoads(self.tags),
            'files': self.jsonLoads(self.files),
            'forms': self.jsonLoads(self.forms)
        }
