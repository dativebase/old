"""Page model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Boolean
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Page(Base):

    __tablename__ = 'page'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Page (%s)>' % self.id

    id = Column(Integer, Sequence('page_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    heading = Column(Unicode(255))
    markupLanguage = Column(Unicode(100))
    content = Column(UnicodeText)
    html = Column(UnicodeText)
    datetimeModified = Column(DateTime, default=now)

