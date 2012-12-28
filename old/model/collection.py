"""Collection model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now
from old.model.form import collectionform_table

collectionfile_table = Table('collectionfile', Base.metadata,
    Column('id', Integer, Sequence('collectionfile_seq_id', optional=True), primary_key=True),
    Column('collection_id', Integer, ForeignKey('collection.id')),
    Column('file_id', Integer, ForeignKey('file.id')),
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
    markupLanguage = Unicode(100)
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
    files = relation('File', secondary=collectionfile_table)
    forms = relation('Form', secondary=collectionform_table)

    def getDict(self):
        """Return a Python dictionary representation of the Collection.  This
        facilitates JSON-stringification, cf. utils.JSONOLDEncoder.  Relational
        data are truncated, e.g., collectionDict['elicitor'] is a dict with keys
        for 'id', 'firstName' and 'lastName' (cf. getMiniUserDict above) and
        lacks keys for other attributes such as 'username',
        'personalPageContent', etc.
        """

        collectionDict = {}
        collectionDict['id'] = self.id
        collectionDict['UUID'] = self.UUID
        collectionDict['title'] = self.title
        collectionDict['type'] = self.type
        collectionDict['url'] = self.url
        collectionDict['description'] = self.description
        collectionDict['markupLanguage'] = self.markupLanguage
        collectionDict['contents'] = self.contents
        collectionDict['html'] = self.html
        collectionDict['dateElicited'] = self.dateElicited
        collectionDict['datetimeEntered'] = self.datetimeEntered
        collectionDict['datetimeModified'] = self.datetimeModified
        collectionDict['speaker'] = self.getMiniSpeakerDict(self.speaker)
        collectionDict['source'] = self.getMiniSourceDict(self.source)
        collectionDict['elicitor'] = self.getMiniUserDict(self.elicitor)
        collectionDict['enterer'] = self.getMiniUserDict(self.enterer)
        collectionDict['files'] = self.getFilesList(self.files)
        collectionDict['forms'] = self.getFormsList(self.forms)
        return collectionDict