"""File model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation
from old.model.meta import Base, now

class File(Base):

    __tablename__ = 'file'

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
