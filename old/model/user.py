"""User model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class UserForm(Base):

    __tablename__ = 'userform'

    id = Column(Integer, Sequence('userform_seq_id', optional=True), primary_key=True)
    form_id = Column(Integer, ForeignKey('form.id'))
    user_id = Column(Integer, ForeignKey('user.id'))
    datetimeModified = Column(DateTime, default=now)

class User(Base):

    __tablename__ = 'user'

    def __repr__(self):
        return "<User (%s)>" % self.id

    id = Column(Integer, Sequence('user_seq_id', optional=True), primary_key=True)
    username = Column(Unicode(255), unique=True)
    password = Column(Unicode(255))
    firstName = Column(Unicode(255))
    lastName = Column(Unicode(255))
    email = Column(Unicode(255))
    affiliation = Column(Unicode(255))
    role = Column(Unicode(255))
    personalPageContent = Column(UnicodeText)
    collectionViewType = Column(Unicode(255), default=u'long')
    inputOrthography = Column(Unicode(255))
    outputOrthography = Column(Unicode(255))
    datetimeModified = Column(DateTime, default=now)
    rememberedForms = relation('Form', secondary=UserForm.__table__, backref='memorizers')
