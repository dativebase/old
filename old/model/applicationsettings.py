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

"""ApplicationSettings model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Boolean
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now
import logging

log = logging.getLogger(__name__)

def deleteKey(dict_, key_):
    """Try to delete the key_ from the dict_; then return the dict_."""
    try:
        del dict_[key_]
    except:
        pass
    return dict_

applicationsettingsuser_table = Table(
    'applicationsettingsuser', Base.metadata,
    Column('id', Integer,
        Sequence('applicationsettingsuser_seq_id', optional=True),
        primary_key=True),
    Column('applicationsettings_id', Integer, ForeignKey('applicationsettings.id')),
    Column('user_id', Integer, ForeignKey('user.id')),
    Column('datetimeModified', DateTime, default=now),
    mysql_charset='utf8'
)

class ApplicationSettings(Base):

    __tablename__ = 'applicationsettings'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return '<ApplicationSettings (%s)>' % self.id

    id = Column(Integer, Sequence('applicationsettings_seq_id', optional=True),
                primary_key=True)
    objectLanguageName = Column(Unicode(255))
    objectLanguageId = Column(Unicode(3))
    metalanguageName = Column(Unicode(255))
    metalanguageId = Column(Unicode(3))
    metalanguageInventory = Column(UnicodeText)
    orthographicValidation = Column(Unicode(7))
    narrowPhoneticInventory = Column(UnicodeText)
    narrowPhoneticValidation = Column(Unicode(7))
    broadPhoneticInventory = Column(UnicodeText)
    broadPhoneticValidation = Column(Unicode(7))
    morphemeBreakIsOrthographic = Column(Boolean)
    morphemeBreakValidation = Column(Unicode(7))
    phonemicInventory = Column(UnicodeText)
    morphemeDelimiters = Column(Unicode(255))
    punctuation = Column(UnicodeText)
    grammaticalities = Column(Unicode(255))
    storageOrthography_id = Column(Integer, ForeignKey('orthography.id'))
    storageOrthography = relation('Orthography',
        primaryjoin='ApplicationSettings.storageOrthography_id==Orthography.id')
    inputOrthography_id = Column(Integer, ForeignKey('orthography.id'))
    inputOrthography = relation('Orthography',
        primaryjoin='ApplicationSettings.inputOrthography_id==Orthography.id')
    outputOrthography_id = Column(Integer, ForeignKey('orthography.id'))
    outputOrthography = relation('Orthography',
        primaryjoin='ApplicationSettings.outputOrthography_id==Orthography.id')
    datetimeModified = Column(DateTime, default=now)
    unrestrictedUsers = relation('User', secondary=applicationsettingsuser_table)

    def getDict(self):
        """Return a Python dictionary representation of the ApplicationSettings.
        This facilitates JSON-stringification, cf. utils.JSONOLDEncoder.
        Relational data are truncated, e.g., applicationSettings.getDict()['storageOrthography']
        is a dict with keys that are a subset of an orthography's attributes.
        """
        return {
            'id': self.id,
            'objectLanguageName': self.objectLanguageName,
            'objectLanguageId': self.objectLanguageId,
            'metalanguageName': self.metalanguageName,
            'metalanguageId': self.metalanguageId,
            'metalanguageInventory': self.metalanguageInventory,
            'orthographicValidation': self.orthographicValidation,
            'narrowPhoneticInventory': self.narrowPhoneticInventory,
            'narrowPhoneticValidation': self.narrowPhoneticValidation,
            'broadPhoneticInventory': self.broadPhoneticInventory,
            'broadPhoneticValidation': self.broadPhoneticValidation,
            'morphemeBreakIsOrthographic': self.morphemeBreakIsOrthographic,
            'morphemeBreakValidation': self.morphemeBreakValidation,
            'phonemicInventory': self.phonemicInventory,
            'morphemeDelimiters': self.morphemeDelimiters,
            'punctuation': self.punctuation,
            'grammaticalities': self.grammaticalities,
            'datetimeModified': self.datetimeModified,
            'storageOrthography': self.getMiniUserDict(self.storageOrthography),
            'inputOrthography': self.getMiniUserDict(self.inputOrthography),
            'outputOrthography': self.getMiniUserDict(self.outputOrthography),
            'unrestrictedUsers': self.getMiniList(self.unrestrictedUsers)
        }
