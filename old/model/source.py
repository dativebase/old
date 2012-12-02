"""Source model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Source(Base):

    __tablename__ = 'source'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Source (%s)>' % self.id

    id = Column(Integer, Sequence('source_seq_id', optional=True), primary_key=True)
    authorFirstName = Column(Unicode(255))
    authorLastName = Column(Unicode(255))
    title = Column(Unicode(255))
    year = Column(Integer)
    fullReference = Column(UnicodeText)
    file_id = Column(Integer, ForeignKey('file.id'))
    file = relation('File')
    datetimeModified = Column(DateTime, default=now)
