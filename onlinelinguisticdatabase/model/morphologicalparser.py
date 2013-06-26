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

"""Morphological parser model"""

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime, Boolean
from sqlalchemy.orm import relation
from onlinelinguisticdatabase.model.meta import Base, now

class MorphologicalParser(Base):

    __tablename__ = 'morphologicalparser'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<MorphologicalParser (%s)>' % self.id

    id = Column(Integer, Sequence('morphologicalparser_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    phonology_id = Column(Integer, ForeignKey('phonology.id'))
    phonology = relation('Phonology')
    morphology_id = Column(Integer, ForeignKey('morphology.id'))
    morphology = relation('Morphology')
    language_model_id = Column(Integer, ForeignKey('morphemelanguagemodel.id'))
    language_model = relation('MorphemeLanguageModel')
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='MorphologicalParser.enterer_id==User.id')
    modifier_id = Column(Integer, ForeignKey('user.id'))
    modifier = relation('User', primaryjoin='MorphologicalParser.modifier_id==User.id')
    datetime_entered = Column(DateTime)
    datetime_modified = Column(DateTime, default=now)
    compile_succeeded = Column(Boolean, default=False)
    compile_message = Column(Unicode(255))
    compile_attempt = Column(Unicode(36)) # a UUID

    def get_dict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'name': self.name,
            'phonology': self.get_mini_dict_for(self.phonology),
            'morphology': self.get_mini_dict_for(self.morphology),
            'language_model': self.get_mini_dict_for(self.language_model),
            'description': self.description,
            'enterer': self.get_mini_user_dict(self.enterer),
            'modifier': self.get_mini_user_dict(self.modifier),
            'datetime_entered': self.datetime_entered,
            'datetime_modified': self.datetime_modified,
            'compile_succeeded': self.compile_succeeded,
            'compile_message': self.compile_message,
            'compile_attempt': self.compile_attempt
        }
