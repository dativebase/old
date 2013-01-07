"""File model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation
from old.model.meta import Base, now

filetag_table = Table('filetag', Base.metadata,
    Column('id', Integer, Sequence('formfile_seq_id', optional=True), primary_key=True),
    Column('file_id', Integer, ForeignKey('file.id')),
    Column('tag_id', Integer, ForeignKey('tag.id')),
    Column('datetimeModified', DateTime(), default=now),
    mysql_charset='utf8'
)

class File(Base):

    __tablename__ = 'file'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<File (%s)>" % self.id

    id = Column(Integer, Sequence('file_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255), unique=True)
    MIMEtype = Column(Unicode(255))
    size = Column(Integer)
    description = Column(UnicodeText)
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='File.enterer_id==User.id')
    elicitor_id = Column(Integer, ForeignKey('user.id'))
    elicitor = relation('User', primaryjoin='File.elicitor_id==User.id')
    speaker_id = Column(Integer, ForeignKey('speaker.id'))
    speaker = relation('Speaker')
    utteranceType = Column(Unicode(255))
    embeddedFileMarkup = Column(UnicodeText)
    embeddedFilePassword = Column(Unicode(255))
    tags = relation('Tag', secondary=filetag_table, backref='files')

    def getDict(self):
        """Return a Python dictionary representation of the File.  This
        facilitates JSON-stringification, cf. utils.JSONOLDEncoder.  Relational
        data are truncated.
        """

        return {
            'id': self.id,
            'dateElicited': self.dateElicited,
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'name': self.name,
            'MIMEtype': self.MIMEtype,
            'size': self.size,
            'description': self.description,
            'utteranceType': self.utteranceType,
            'embeddedFileMarkup': self.embeddedFileMarkup,
            'embeddedFilePassword': self.embeddedFilePassword,
            'enterer': self.getMiniUserDict(self.enterer),
            'elicitor': self.getMiniUserDict(self.elicitor),
            'speaker': self.getMiniSpeakerDict(self.speaker),
            'tags': self.getTagsList(self.tags),
            'forms': self.getFormsList(self.forms)
        }