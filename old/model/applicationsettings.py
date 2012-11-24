"""ApplicationSettings model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime, Boolean
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

def deleteKey(dict_, key_):
    """Try to delete the key_ from the dict_; then return the dict_."""
    try:
        del dict_[key_]
    except:
        pass
    return dict_


applicationsettingsorthography_table = Table(
    'applicationsettingsorthography', Base.metadata,
    Column('id', Integer,
        Sequence('applicationsettingsorthography_seq_id', optional=True),
        primary_key=True),
    Column('applicationsettings_id', Integer, ForeignKey('applicationsettings.id')),
    Column('orthography_id', Integer, ForeignKey('orthography.id')),
    Column('datetimeModified', DateTime, default=now)
)

applicationsettingsuser_table = Table(
    'applicationsettingsuser', Base.metadata,
    Column('id', Integer,
        Sequence('applicationsettingsuser_seq_id', optional=True),
        primary_key=True),
    Column('applicationsettings_id', Integer, ForeignKey('applicationsettings.id')),
    Column('user_id', Integer, ForeignKey('user.id')),
    Column('datetimeModified', DateTime, default=now)
)

class ApplicationSettings(Base):

    __tablename__ = 'applicationsettings'

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
    orthographies = relation('Orthography',
                             secondary=applicationsettingsorthography_table)
    unrestrictedUsers = relation('User', secondary=applicationsettingsuser_table)

    def getDict(self):
        """Return a Python dictionary representation of the ApplicationSettings.
        This facilitates JSON-stringification, cf. utils.JSONOLDEncoder.
        Relational data are truncated, e.g., ...

        TODO: ...formDict['elicitor'] is a dict with keys for
        'id', 'firstName' and 'lastName' (cf. getMiniUserDict above) and lacks
        keys for other attributes such as 'username', 'personalPageContent', etc.
        """

        applicationSettingsDict = {}
        applicationSettingsDict['id'] = self.id
        applicationSettingsDict['objectLanguageName'] = self.objectLanguageName
        applicationSettingsDict['objectLanguageId'] = self.objectLanguageId
        applicationSettingsDict['metalanguageName'] = self.metalanguageName
        applicationSettingsDict['metalanguageId'] = self.metalanguageId
        applicationSettingsDict['metalanguageInventory'] = self.metalanguageInventory
        applicationSettingsDict['orthographicValidation'] = self.orthographicValidation
        applicationSettingsDict['narrowPhoneticInventory'] = self.narrowPhoneticInventory
        applicationSettingsDict['narrowPhoneticValidation'] = self.narrowPhoneticValidation
        applicationSettingsDict['broadPhoneticInventory'] = self.broadPhoneticInventory
        applicationSettingsDict['broadPhoneticValidation'] = self.broadPhoneticValidation
        applicationSettingsDict['morphemeBreakIsOrthographic'] = self.morphemeBreakIsOrthographic
        applicationSettingsDict['morphemeBreakValidation'] = self.morphemeBreakValidation
        applicationSettingsDict['phonemicInventory'] = self.phonemicInventory
        applicationSettingsDict['morphemeDelimiters'] = self.morphemeDelimiters
        applicationSettingsDict['punctuation'] = self.punctuation
        applicationSettingsDict['grammaticalities'] = self.grammaticalities
        applicationSettingsDict['datetimeModified'] = self.datetimeModified
        applicationSettingsDict['storageOrthography'] = self.getMiniOrthographyDict(
            self.storageOrthography)
        applicationSettingsDict['inputOrthography'] = self.getMiniOrthographyDict(
            self.inputOrthography)
        applicationSettingsDict['outputOrthography'] = self.getMiniOrthographyDict(
            self.outputOrthography)
        applicationSettingsDict['orthographies'] = self.getOrthographiesList(
            self.orthographies)
        applicationSettingsDict['unrestrictedUsers'] = [
            deleteKey(user.__dict__, 'password') for user in self.unrestrictedUsers]
        return applicationSettingsDict
