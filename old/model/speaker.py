"""Speaker model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Speaker(Base):

    __tablename__ = 'speaker'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Speaker (%s)>' % self.id

    id = Column(Integer, Sequence('speaker_seq_id', optional=True), primary_key=True)
    firstName = Column(Unicode(255))
    lastName = Column(Unicode(255))
    dialect = Column(Unicode(255))
    pageContent = Column(UnicodeText)
    datetimeModified = Column(DateTime, default=now)

    def getDict(self):
        return {
            'id': self.id,
            'firstName': self.firstName,
            'lastName': self.lastName,
            'dialect': self.dialect,
            'pageContent': self.pageContent,
            'datetimeModified': self.datetimeModified
        }