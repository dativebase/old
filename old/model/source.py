"""Source model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Source(Base):

    __tablename__ = 'source'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Source (%s)>' % self.id

    id = Column(Integer, Sequence('source_seq_id', optional=True), primary_key=True)
    file_id = Column(Integer, ForeignKey('file.id'))
    file = relation('File')
    datetimeModified = Column(DateTime, default=now)

    # BibTeX data structure
    type = Column(Unicode(20))
    key = Column(Unicode(1000))

    # BibTeX fields
    address = Column(Unicode(1000))
    annote = Column(UnicodeText)
    author = Column(Unicode(255))
    booktitle = Column(Unicode(255))
    chapter = Column(Unicode(255))
    crossref = Column(Unicode(255))
    edition = Column(Unicode(255))
    editor = Column(Unicode(255))
    howpublished = Column(Unicode(255))
    institution = Column(Unicode(255))
    journal = Column(Unicode(255))
    keyField = Column(Unicode(255))
    month = Column(Unicode(100))
    note = Column(Unicode(1000))
    number = Column(Unicode(100))
    organization = Column(Unicode(255))
    pages = Column(Unicode(100))
    publisher = Column(Unicode(255))
    school = Column(Unicode(255))
    series = Column(Unicode(255))
    title = Column(Unicode(255))
    typeField = Column(Unicode(255))
    url = Column(Unicode(1000))
    volume = Column(Unicode(100))
    year = Column(Integer)

    # Non-standard BibTeX fields
    affiliation = Column(Unicode(255))
    abstract = Column(Unicode(1000))
    contents = Column(Unicode(255))
    copyright = Column(Unicode(255))
    ISBN = Column(Unicode(20))
    ISSN = Column(Unicode(20))
    keywords = Column(Unicode(255))
    language = Column(Unicode(255))
    location = Column(Unicode(255))
    LCCN = Column(Unicode(20))
    mrnumber = Column(Unicode(25))
    price = Column(Unicode(100))
    size = Column(Unicode(255))

    def getDict(self):
        """Return a Python dictionary representation of the Source.  This
        facilitates JSON-stringification, cf. utils.JSONOLDEncoder.  Relational
        data are truncated, e.g., sourceDict['file'] is a dict with keys for
        'name', 'size', etc. (cf. getMiniUserDict of the model superclass) and
        lacks keys for some attributes.
        """

        sourceDict = self.__dict__
        sourceDict['file'] = self.getMiniFileDict(self.file)
        return sourceDict
