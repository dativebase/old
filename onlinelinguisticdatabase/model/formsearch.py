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

"""FormSearch model"""

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime
from sqlalchemy.orm import relation
from onlinelinguisticdatabase.model.meta import Base, now
import logging
log = logging.getLogger(__name__)

class FormSearch(Base):

    __tablename__ = 'formsearch'

    def __repr__(self):
        return '<FormSearch (%s)>' % self.id

    id = Column(Integer, Sequence('formsearch_seq_id', optional=True), primary_key=True)
    name = Column(Unicode(255))
    search = Column(UnicodeText)    # The search params as JSON
    description = Column(UnicodeText)
    enterer_id = Column(Integer, ForeignKey('user.id', ondelete='SET NULL'))
    enterer = relation('User')
    datetime_modified = Column(DateTime, default=now)

    def get_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'search': self.json_loads(self.search),
            'description': self.description,
            'enterer': self.get_mini_user_dict(self.enterer),
            'datetime_modified': self.datetime_modified
        }
