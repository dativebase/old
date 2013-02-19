# Copyright 2013 Joel Dunham
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""File model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Float
from sqlalchemy.orm import relation
from onlinelinguisticdatabase.model.meta import Base, now

import logging
log = logging.getLogger(__name__)

filetag_table = Table('filetag', Base.metadata,
    Column('id', Integer, Sequence('formfile_seq_id', optional=True), primary_key=True),
    Column('file_id', Integer, ForeignKey('file.id')),
    Column('tag_id', Integer, ForeignKey('tag.id')),
    Column('datetimeModified', DateTime(), default=now),
    mysql_charset='utf8'
)

class File(Base):
    """There are 3 types of file:
    
    1. Standard files: their content is a file in /files/filename.  These files
       have a filename attribute.
    2. Subinterval-referring A/V files: these refer to another OLD file for
       their content.  These files have a parentFile attribute (as well as start
       and end attributes.)
    3. Externally hosted files: these refer to a file hosted on another server.
       They have a url attribute (and optionally a password attribute as well.)
    """

    __tablename__ = 'file'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<File (%s)>" % self.id

    id = Column(Integer, Sequence('file_seq_id', optional=True), primary_key=True)
    filename = Column(Unicode(255), unique=True)    # filename is the name of the file as written to disk
    name = Column(Unicode(255))                     # just a name; useful for subinterval-referencing files; need not be unique
    MIMEtype = Column(Unicode(255))
    size = Column(Integer)
    description = Column(UnicodeText)
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='File.enterer_id==User.id')
    elicitor_id = Column(Integer, ForeignKey('user.id'))
    elicitor = relation('User', primaryjoin='File.elicitor_id==User.id')
    speaker_id = Column(Integer, ForeignKey('speaker.id'))
    speaker = relation('Speaker')
    utteranceType = Column(Unicode(255))
    tags = relation('Tag', secondary=filetag_table, backref='files')

    # Attributes germane to externally hosted files.
    url = Column(Unicode(255))          # for external files
    password = Column(Unicode(255))     # for external files requiring authentication

    # Attributes germane to subinterval-referencing a/v files.
    parentFile_id = Column(Integer, ForeignKey('file.id'))
    parentFile = relation('File', remote_side=[id])
    start = Column(Float)
    end = Column(Float)

    lossyFilename = Column(Unicode(255))        # .ogg generated from .wav or resized images

    def getDict(self):
        """Return a Python dictionary representation of the File.  This
        facilitates JSON-stringification, cf. utils.JSONOLDEncoder.  Relational
        data are truncated.
        """
        return {
            'id': self.id,
            'dateElicited': self.dateElicited,
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'filename': self.filename,
            'name': self.name,
            'lossyFilename': self.lossyFilename,
            'MIMEtype': self.MIMEtype,
            'size': self.size,
            'description': self.description,
            'utteranceType': self.utteranceType,
            'url': self.url,
            'password': self.password,
            'enterer': self.getMiniUserDict(self.enterer),
            'elicitor': self.getMiniUserDict(self.elicitor),
            'speaker': self.getMiniSpeakerDict(self.speaker),
            'tags': self.getTagsList(self.tags),
            'forms': self.getFormsList(self.forms),
            'parentFile': self.getMiniFileDict(self.parentFile),
            'start': self.start,
            'end': self.end
        }
