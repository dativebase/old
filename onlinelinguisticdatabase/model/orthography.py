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

"""Orthography model"""

from sqlalchemy import Column, Sequence
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime, Boolean
from onlinelinguisticdatabase.model.meta import Base, now

class Orthography(Base):

    __tablename__ = 'orthography'

    def __repr__(self):
        return '<Orthography (%s)>' % self.id

    id = Column(Integer, Sequence('orthography_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    orthography = Column(UnicodeText)
    lowercase = Column(Boolean, default=False)
    initial_glottal_stops = Column(Boolean, default=True)
    datetime_modified = Column(DateTime, default=now)
