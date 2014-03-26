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

"""Language model"""

from sqlalchemy import Column
from sqlalchemy.types import Unicode, DateTime
from onlinelinguisticdatabase.model.meta import Base, now

class Language(Base):

    __tablename__ = 'language'

    def __repr__(self):
        return '<Language (%s)>' % self.Id

    Id = Column(Unicode(3), primary_key=True)
    Part2B = Column(Unicode(3))
    Part2T = Column(Unicode(3))
    Part1 = Column(Unicode(2))
    Scope = Column(Unicode(1))
    Type = Column(Unicode(1))
    Ref_Name = Column(Unicode(150))
    Comment = Column(Unicode(150))
    datetime_modified = Column(DateTime, default=now)
