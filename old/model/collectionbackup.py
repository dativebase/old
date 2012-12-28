"""CollectionBackup model

Used to save Collection data that has been updated or deleted.  This is a
non-relational table, because keeping a copy of every single change relationally
seemed like more trouble than it's worth.
"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now


class CollectionBackup(Base):

    __tablename__ = "collectionbackup"
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<CollectionBackup (%s)>" % self.id

    id = Column(Integer, Sequence('collectionbackup_seq_id', optional=True), primary_key=True)
    collection_id = Column(Integer)
    UUID = Column(Unicode(36))
    title = Column(Unicode(255))
    type = Column(Unicode(255))
    url = Column(Unicode(255))
    description = Column(UnicodeText)
    markupLanguage = Unicode(100)
    contents = Column(UnicodeText)
    html = Column(UnicodeText)
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    speaker = Column(UnicodeText)
    source = Column(UnicodeText)
    elicitor = Column(UnicodeText)
    enterer = Column(UnicodeText)
    backuper = Column(UnicodeText)
    files = Column(UnicodeText)
    forms = Column(UnicodeText)
