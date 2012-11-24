"""Form model"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now

class FormFile(Base):

    __tablename__ = 'formfile'

    id = Column(Integer, Sequence('formfile_seq_id', optional=True), primary_key=True)
    form_id = Column(Integer, ForeignKey('form.id'))
    file_id = Column(Integer, ForeignKey('file.id'))
    datetimeModified = Column(DateTime, default=now)

formtag_table = Table('formtag', Base.metadata,
    Column('id', Integer, Sequence('formfile_seq_id', optional=True), primary_key=True),
    Column('form_id', Integer, ForeignKey('form.id')),
    Column('tag_id', Integer, ForeignKey('tag.id')),
    Column('datetimeModified', DateTime(), default=now)
)

collectionform_table = Table('collectionform', Base.metadata,
    Column('id', Integer, Sequence('collectionform_seq_id', optional=True), primary_key=True),
    Column('collection_id', Integer, ForeignKey('collection.id')),
    Column('form_id', Integer, ForeignKey('form.id')),
    Column('datetimeModified', DateTime(), default=now)
)

class Form(Base):
    __tablename__ = "form"

    def __repr__(self):
        return "<Form (%s)>" % self.id

    id = Column(Integer, Sequence('form_seq_id', optional=True), primary_key=True)
    UUID = Column(Unicode(36))
    transcription = Column(Unicode(255), nullable=False)
    phoneticTranscription = Column(Unicode(255))
    narrowPhoneticTranscription = Column(Unicode(255))
    morphemeBreak = Column(Unicode(255))
    morphemeGloss = Column(Unicode(255))
    comments = Column(UnicodeText)
    speakerComments = Column(UnicodeText)
    grammaticality = Column(Unicode(255))
    dateElicited = Column(Date)
    datetimeEntered = Column(DateTime)
    datetimeModified = Column(DateTime, default=now)
    syntacticCategoryString = Column(Unicode(255))
    morphemeBreakIDs = Column(UnicodeText)
    morphemeGlossIDs = Column(UnicodeText)
    breakGlossCategory = Column(Unicode(1023))
    syntax = Column(Unicode(1023))
    semantics = Column(Unicode(1023))
    elicitor_id = Column(Integer, ForeignKey('user.id'))
    elicitor = relation('User', primaryjoin='Form.elicitor_id==User.id')
    enterer_id = Column(Integer, ForeignKey('user.id'))
    enterer = relation('User', primaryjoin='Form.enterer_id==User.id')
    verifier_id = Column(Integer, ForeignKey('user.id'))
    verifier = relation('User', primaryjoin='Form.verifier_id==User.id')
    speaker_id = Column(Integer, ForeignKey('speaker.id'))
    speaker = relation('Speaker')
    elicitationmethod_id = Column(Integer, ForeignKey('elicitationmethod.id'))
    elicitationMethod = relation('ElicitationMethod')
    syntacticcategory_id = Column(Integer, ForeignKey('syntacticcategory.id'))
    syntacticCategory = relation('SyntacticCategory')
    source_id = Column(Integer, ForeignKey('source.id'))
    source = relation('Source')
    glosses = relation('Gloss', backref='form', cascade='all, delete, delete-orphan')
    files = relation('File', secondary=FormFile.__table__, backref='forms')
    collections = relation('Collection', secondary=collectionform_table)
    tags = relation('Tag', secondary=formtag_table, backref='forms')
    def getDict(self):
        """Return a Python dictionary representation of the Form.  This
        facilitates JSON-stringification, cf. utils.JSONOLDEncoder.  Relational
        data are truncated, e.g., formDict['elicitor'] is a dict with keys for
        'id', 'firstName' and 'lastName' (cf. getMiniUserDict above) and lacks
        keys for other attributes such as 'username', 'personalPageContent', etc.
        """

        formDict = {}
        formDict['id'] = self.id
        formDict['UUID'] = self.UUID
        formDict['transcription'] = self.transcription
        formDict['phoneticTranscription'] = self.phoneticTranscription
        formDict['narrowPhoneticTranscription'] = self.narrowPhoneticTranscription
        formDict['morphemeBreak'] = self.morphemeBreak
        formDict['morphemeGloss'] = self.morphemeGloss
        formDict['comments'] = self.comments
        formDict['speakerComments'] = self.speakerComments
        formDict['grammaticality'] = self.grammaticality
        formDict['dateElicited'] = self.dateElicited
        formDict['datetimeEntered'] = self.datetimeEntered
        formDict['datetimeModified'] = self.datetimeModified
        formDict['syntacticCategoryString'] = self.syntacticCategoryString
        formDict['morphemeBreakIDs'] = self.jsonLoads(self.morphemeBreakIDs)
        formDict['morphemeGlossIDs'] = self.jsonLoads(self.morphemeGlossIDs)
        formDict['breakGlossCategory'] = self.breakGlossCategory
        formDict['elicitor'] = self.getMiniUserDict(self.elicitor)
        formDict['enterer'] = self.getMiniUserDict(self.enterer)
        formDict['verifier'] = self.getMiniUserDict(self.verifier)
        formDict['speaker'] = self.getMiniSpeakerDict(self.speaker)
        formDict['elicitationMethod'] = self.getMiniElicitationMethodDict(
            self.elicitationMethod)
        formDict['syntacticCategory'] = self.getMiniSyntacticCategoryDict(
            self.syntacticCategory)
        formDict['source'] = self.getMiniSourceDict(self.source)
        formDict['glosses'] = self.getGlossesList(self.glosses)
        formDict['tags'] = self.getTagsList(self.tags)
        formDict['files'] = self.getFilesList(self.files)
        return formDict
