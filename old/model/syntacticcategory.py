"""SyntacticCategory model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class SyntacticCategory(Base):

    __tablename__ = 'syntacticcategory'

    def __repr__(self):
        return '<SyntacticCategory (%s)>' % self.id

    id = Column(Integer, Sequence('syntacticcategory_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    type = Column(Unicode(60))
    description = Column(UnicodeText)
    datetimeModified = Column(DateTime, default=now)
