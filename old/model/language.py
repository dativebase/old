"""Language model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Unicode, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Language(Base):

    __tablename__ = 'language'

    def __repr__(self):
        return '<Language (%s)>' % self.Id

    Id = Column(Unicode(3), primary_key=True)
    Part2B = Column(Unicode(3))
    Part2T = Column(Unicode(3))
    Part1 = Column(Unicode(2))
    Scope = Column(Unicode(1))
    Type = Column(Unicode(1))
    Ref_Name = Column(Unicode(150))
    Comment = Column(Unicode(150))
    datetimeModified = Column(DateTime, default=now)
