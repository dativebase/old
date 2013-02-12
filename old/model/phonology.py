"""Phonology model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Boolean
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Phonology(Base):

    __tablename__ = 'phonology'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Phonology (%s)>' % self.id

    id = Column(Integer, Sequence('phonology_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    script = Column(UnicodeText)
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='Phonology.enterer_id==User.id')
    modifier_id = Column(Integer, ForeignKey('user.id'))
    modifier = relation('User', primaryjoin='Phonology.modifier_id==User.id')
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)

    def getDict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'script': self.getMiniUserDict(self.script),
            'enterer': self.getMiniUserDict(self.enterer),
            'modifier': self.modifier,
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified
        }
