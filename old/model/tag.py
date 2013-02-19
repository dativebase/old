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

"""Tag model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class Tag(Base):

    __tablename__ = 'tag'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Tag (%s)>' % self.id

    id = Column(Integer, Sequence('tag_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255), unique=True)
    description = Column(UnicodeText)
    datetimeModified = Column(DateTime, default=now)

    def getDict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'datetimeModified': self.datetimeModified
        }
