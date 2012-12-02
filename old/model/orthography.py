"""Orthography model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Boolean
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Orthography(Base):

    __tablename__ = 'orthography'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Orthography (%s)>' % self.id

    id = Column(Integer, Sequence('orthography_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    orthography = Column(UnicodeText)
    lowercase = Column(Boolean)
    initialGlottalStops = Column(Boolean)
    datetimeModified = Column(DateTime, default=now)
