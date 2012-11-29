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

    def __repr__(self):
        return "<CollectionBackup (%s)>" % self.id

    id = Column(Integer, Sequence('collectionbackup_seq_id', optional=True), primary_key=True)
    collection_id = Column(Integer)
    title = Column(Unicode(255))
    type = Column(Unicode(255))
    url = Column(Unicode(255))
    description = Column(UnicodeText)
    contents = Column(UnicodeText)
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    speaker = Column(Unicode(255))
    source = Column(UnicodeText)
    elicitor = Column(Unicode(255))
    enterer = Column(Unicode(255))
    backuper = Column(Unicode(255))
    files = Column(UnicodeText)
