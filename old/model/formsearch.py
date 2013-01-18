"""FormSearch model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Boolean
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class FormSearch(Base):

    __tablename__ = 'formsearch'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<FormSearch (%s)>' % self.id

    id = Column(Integer, Sequence('formsearch_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    search = Column(UnicodeText)    # The search params as JSON
    description = Column(UnicodeText)
    searcher_id = Column(Integer, ForeignKey('user.id'))
    searcher = relation('User')
    datetimeModified = Column(DateTime, default=now)
