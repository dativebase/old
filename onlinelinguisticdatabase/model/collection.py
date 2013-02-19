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

"""Collection model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from onlinelinguisticdatabase.model.meta import Base, now

collectionfile_table = Table('collectionfile', Base.metadata,
    Column('id', Integer, Sequence('collectionfile_seq_id', optional=True), primary_key=True),
    Column('collection_id', Integer, ForeignKey('collection.id')),
    Column('file_id', Integer, ForeignKey('file.id')),
    Column('datetimeModified', DateTime(), default=now),
    mysql_charset='utf8'
)

collectiontag_table = Table('collectiontag', Base.metadata,
    Column('id', Integer, Sequence('collectiontag_seq_id', optional=True), primary_key=True),
    Column('collection_id', Integer, ForeignKey('collection.id')),
    Column('tag_id', Integer, ForeignKey('tag.id')),
    Column('datetimeModified', DateTime(), default=now),
    mysql_charset='utf8'
)

class Collection(Base):

    __tablename__ = 'collection'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<Collection (%s)>" % self.id

    id = Column(Integer, Sequence('collection_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36))
    title = Column(Unicode(255))
    type = Column(Unicode(255))
    url = Column(Unicode(255))
    description = Column(UnicodeText)
    markupLanguage = Column(Unicode(100))
    contents = Column(UnicodeText)
    html = Column(UnicodeText)
    speaker_id = Column(Integer, ForeignKey('speaker.id'))
    speaker = relation('Speaker')
    source_id = Column(Integer, ForeignKey('source.id'))
    source = relation('Source')
    elicitor_id = Column(Integer, ForeignKey('user.id'))
    elicitor = relation('User', primaryjoin='Collection.elicitor_id==User.id')
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='Collection.enterer_id==User.id')
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    tags = relation('Tag', secondary=collectiontag_table)
    files = relation('File', secondary=collectionfile_table, backref='collections')
    # forms attribute is defined in a relation/backref in the form model

    # The contentsUnpacked column holds the contents of the collection where all
    # collection references in the contents field are replaced with the contents
    # of the referred-to collections.  These referred-to collections can refer
    # to others in turn.  The forms related to a collection are calculated by
    # gathering the form references from contentsUnpacked.  The result of all
    # this is that the contents (and form references) of a collection can be
    # altered by updates to another collection; however, these updates will not
    # propagate until the collection in question is itself updated.
    contentsUnpacked = Column(UnicodeText)

    def getDict(self):
        """Return a Python dictionary representation of the Collection.  This
        facilitates JSON-stringification, cf. utils.JSONOLDEncoder.  Relational
        data are truncated, e.g., collectionDict['elicitor'] is a dict with keys
        for 'id', 'firstName' and 'lastName' (cf. getMiniUserDict above) and
        lacks keys for other attributes such as 'username',
        'personalPageContent', etc.
        """

        return {
            'id': self.id,
            'UUID': self.UUID,
            'title': self.title,
            'type': self.type,
            'url': self.url,
            'description': self.description,
            'markupLanguage': self.markupLanguage,
            'contents': self.contents,
            'contentsUnpacked': self.contentsUnpacked,
            'html': self.html,
            'dateElicited': self.dateElicited,
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'speaker': self.getMiniSpeakerDict(self.speaker),
            'source': self.getMiniSourceDict(self.source),
            'elicitor': self.getMiniUserDict(self.elicitor),
            'enterer': self.getMiniUserDict(self.enterer),
            'tags': self.getTagsList(self.tags),
            'files': self.getFilesList(self.files),
            'forms': self.getFormsList(self.forms)
        }
