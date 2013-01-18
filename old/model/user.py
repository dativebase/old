"""User model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class UserForm(Base):

    __tablename__ = 'userform'
    __table_args__ = {'mysql_charset': 'utf8'}

    id = Column(Integer, Sequence('userform_seq_id', optional=True), primary_key=True)
    form_id = Column(Integer, ForeignKey('form.id'))
    user_id = Column(Integer, ForeignKey('user.id'))
    datetimeModified = Column(DateTime, default=now)

class User(Base):

    __tablename__ = 'user'
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<User (%s)>" % self.id

    id = Column(Integer, Sequence('user_seq_id', optional=True), primary_key=True)
    username = Column(Unicode(255), unique=True)
    password = Column(Unicode(255))
    salt = Column(Unicode(255))
    firstName = Column(Unicode(255))
    lastName = Column(Unicode(255))
    email = Column(Unicode(255))
    affiliation = Column(Unicode(255))
    role = Column(Unicode(100))
    markupLanguage = Column(Unicode(100))
    pageContent = Column(UnicodeText)
    html = Column(UnicodeText)
    inputOrthography_id = Column(Integer, ForeignKey('orthography.id'))
    inputOrthography = relation('Orthography',
        primaryjoin='User.inputOrthography_id==Orthography.id')
    outputOrthography_id = Column(Integer, ForeignKey('orthography.id'))
    outputOrthography = relation('Orthography',
        primaryjoin='User.outputOrthography_id==Orthography.id')
    datetimeModified = Column(DateTime, default=now)
    rememberedForms = relation('Form', secondary=UserForm.__table__, backref='memorizers')

    def getDict(self):
        return {
            'id': self.id,
            'firstName': self.firstName,
            'lastName': self.lastName,
            'email': self.email,
            'affiliation': self.affiliation,
            'role': self.role,
            'markupLanguage': self.markupLanguage,
            'pageContent': self.pageContent,
            'html': self.html,
            'inputOrthography': self.getMiniOrthographyDict(self.inputOrthography),
            'outputOrthography': self.getMiniOrthographyDict(self.outputOrthography),
            'datetimeModified': self.datetimeModified
        }

    def getFullDict(self):
        userDict = self.getDict()
        userDict['username'] = self.username
        return userDict