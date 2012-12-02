"""Gloss model"""

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Gloss(Base):

    __tablename__ = 'gloss'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Gloss (%s)>' % self.id

    id = Column(Integer, Sequence('gloss_seq_id', optional=True), primary_key=True)
    gloss = Column(UnicodeText, nullable=False)
    glossGrammaticality = Column(Unicode(255))
    form_id = Column(Integer, ForeignKey('form.id'))
    datetimeModified = Column(DateTime, default=now)
