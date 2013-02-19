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

"""Gloss model"""

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime
from sqlalchemy.orm import relation, backref
from onlinelinguisticdatabase.model.meta import Base, now

class Gloss(Base):

    __tablename__ = 'gloss'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<Gloss (%s)>' % self.id

    id = Column(Integer, Sequence('gloss_seq_id', optional=True), primary_key=True)
    gloss = Column(UnicodeText, nullable=False)
    glossGrammaticality = Column(Unicode(255))
    form_id = Column(Integer, ForeignKey('form.id'))
    datetimeModified = Column(DateTime, default=now)
