"""Collection model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now
from old.model.form import collectionform_table

collectionfile_table = Table('collectionfile', Base.metadata,
    Column('id', Integer, Sequence('collectionfile_seq_id', optional=True), primary_key=True),
    Column('collection_id', Integer, ForeignKey('collection.id')),
    Column('file_id', Integer, ForeignKey('file.id')),
    Column('datetimeModified', DateTime(), default=now)
)

class Collection(Base):

    __tablename__ = 'collection'

    def __repr__(self):
        return "<Collection (%s)>" % self.id

    id = Column(Integer, Sequence('collection_seq_id', optional=True), primary_key=True)
    title = Column(Unicode(255))
    type = Column(Unicode(255))
    url = Column(Unicode(255))
    speaker_id = Column(Integer, ForeignKey('speaker.id'))
    speaker = relation('Speaker')
    source_id = Column(Integer, ForeignKey('source.id'))
    source = relation('Source')
    elicitor_id = Column(Integer, ForeignKey('user.id'))
    elicitor = relation('User', primaryjoin='Collection.elicitor_id==User.id')
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='Collection.enterer_id==User.id')
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    description = Column(UnicodeText)
    contents = Column(UnicodeText)
    files = relation('File', secondary=collectionfile_table)
    forms = relation('Form', secondary=collectionform_table)
