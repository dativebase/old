"""ElicitationMethod model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class ElicitationMethod(Base):

    __tablename__ = 'elicitationmethod'

    def __repr__(self):
        return '<ElicitationMethod (%s)>' % self.id

    id = Column(Integer, Sequence('elicitationmethod_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    datetimeModified = Column(DateTime, default=now)
