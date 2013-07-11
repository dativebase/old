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

"""Morpheme language model model"""

from sqlalchemy import Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, DateTime, Boolean, Float
from sqlalchemy.orm import relation
from onlinelinguisticdatabase.model.meta import Base, now

class MorphemeLanguageModel(Base):
    """The OLD currently uses the MITLM toolkit to build its language models. 
    Support for CMU-Cambridge, SRILM, KenLM, etc. may be forthcoming...

    """
    __tablename__ = 'morphemelanguagemodel'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<MorphemeLanguageModel (%s)>' % self.id

    id = Column(Integer, Sequence('morphemelanguagemodel_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36))
    name = Column(Unicode(255))
    description = Column(UnicodeText)
    corpus_id = Column(Integer, ForeignKey('corpus.id'))
    corpus = relation('Corpus') # whence we extract the morpheme sequences and their counts
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='MorphemeLanguageModel.enterer_id==User.id')
    modifier_id = Column(Integer, ForeignKey('user.id'))
    modifier = relation('User', primaryjoin='MorphemeLanguageModel.modifier_id==User.id')
    datetime_entered = Column(DateTime)
    datetime_modified = Column(DateTime, default=now)
    generate_succeeded = Column(Boolean, default=False)
    generate_message = Column(Unicode(255))
    generate_attempt = Column(Unicode(36)) # a UUID
    perplexity = Column(Float, default=0.0)
    perplexity_attempt = Column(Unicode(36)) # a UUID
    perplexity_computed = Column(Boolean, default=False)
    toolkit = Column(Unicode(10))
    order = Column(Integer, default=3)
    smoothing = Column(Unicode(30))
    vocabulary_morphology_id = Column(Integer, ForeignKey('morphology.id'))
    vocabulary_morphology = relation('Morphology') # if specified, LM will use the lexicon of the morphology as the fixed vocabulary
    restricted = Column(Boolean, default=False)
    categorial = Column(Boolean, default=False) # if True, the model will be built over sequences of categories, not morphemes

    def get_dict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'name': self.name,
            'corpus': self.get_mini_dict_for(self.corpus),
            'description': self.description,
            'enterer': self.get_mini_user_dict(self.enterer),
            'modifier': self.get_mini_user_dict(self.modifier),
            'datetime_entered': self.datetime_entered,
            'datetime_modified': self.datetime_modified,
            'generate_succeeded': self.generate_succeeded,
            'generate_message': self.generate_message,
            'generate_attempt': self.generate_attempt,
            'perplexity': self.perplexity,
            'perplexity_attempt': self.perplexity_attempt,
            'perplexity_computed': self.perplexity_computed,
            'toolkit': self.toolkit,
            'order': self.order,
            'smoothing': self.smoothing,
            'vocabulary_morphology': self.get_mini_dict_for(self.vocabulary_morphology),
            'restricted': self.restricted,
            'categorial': self.categorial
        }

