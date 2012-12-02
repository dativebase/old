"""FormBackup model

Used to save Form data that has been updated or deleted.  This is a
non-relational table, because keeping a copy of every single change relationally
seemed like more trouble than it's worth.
"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from old.model.meta import Base, now
import simplejson as json
import datetime

class FormBackup(Base):
    """Class for creating OLD FormBackup models.

    The vivify method takes a Form and a User object as input and populates a
    number of Form-like attributes, converting relational attributes to JSON
    objects.

    The load method converts the JSON objects into Python Column objects, thus
    allowing the FormBackup to behave more like a Form object.
    """

    __tablename__ = "formbackup"
    __table_args__ = {'mysql_charset': 'utf8'}

    def __repr__(self):
        return "<FormBackup (%s)>" % self.id

    id = Column(Integer, Sequence('formbackup_seq_id', optional=True), primary_key=True)
    form_id = Column(Integer)
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
    elicitor = Column(UnicodeText)
    enterer = Column(UnicodeText)
    verifier = Column(UnicodeText)
    speaker = Column(UnicodeText)
    elicitationMethod = Column(UnicodeText)
    syntacticCategory = Column(UnicodeText)
    source = Column(UnicodeText)
    glosses = Column(UnicodeText)
    tags = Column(UnicodeText)
    files = Column(UnicodeText) 
    backuper = Column(UnicodeText)

    def vivify(self, formDict, backuper, datetimeModified=None):
        """The vivify method gives life to FormBackup by specifying its
        attributes using the to-be-backed-up form (formDict) and the backuper
        (current user).  The relational attributes of the to-be-backed-up form
        are converted into (truncated) JSON objects.
        """

        self.UUID = formDict['UUID']
        self.form_id = formDict['id']
        self.transcription = formDict['transcription']
        self.phoneticTranscription = formDict['phoneticTranscription']
        self.narrowPhoneticTranscription = formDict['narrowPhoneticTranscription']
        self.morphemeBreak = formDict['morphemeBreak']
        self.morphemeGloss = formDict['morphemeGloss']
        self.grammaticality = formDict['grammaticality']
        self.comments = formDict['comments']
        self.speakerComments = formDict['speakerComments']
        self.dateElicited = formDict['dateElicited']
        self.datetimeEntered = formDict['datetimeEntered']
        if datetimeModified:
            self.datetimeModified = datetimeModified
        else:
            self.datetimeModified = datetime.datetime.utcnow()
        self.syntacticCategoryString = formDict['syntacticCategoryString']
        self.morphemeBreakIDs = unicode(json.dumps(formDict['morphemeBreakIDs']))
        self.morphemeGlossIDs = unicode(json.dumps(formDict['morphemeGlossIDs']))
        self.breakGlossCategory = formDict['breakGlossCategory']
        self.elicitationMethod = unicode(json.dumps(formDict['elicitationMethod']))
        self.syntacticCategory = unicode(json.dumps(formDict['syntacticCategory']))
        self.source = unicode(json.dumps(formDict['source']))
        self.speaker = unicode(json.dumps(formDict['speaker']))
        self.elicitor = unicode(json.dumps(formDict['elicitor']))
        self.enterer = unicode(json.dumps(formDict['enterer']))
        self.verifier = unicode(json.dumps(formDict['verifier']))
        self.backuper = unicode(json.dumps(self.getMiniUserDict(backuper)))
        self.glosses = unicode(json.dumps(formDict['glosses']))
        self.tags = unicode(json.dumps(formDict['tags']))
        self.files = unicode(json.dumps(formDict['files']))

    def getDict(self):
        formBackupDict = {}
        formBackupDict['UUID'] = self.UUID
        formBackupDict['form_id'] = self.form_id
        formBackupDict['transcription'] = self.transcription
        formBackupDict['phoneticTranscription'] = self.phoneticTranscription
        formBackupDict['narrowPhoneticTranscription'] = self.narrowPhoneticTranscription
        formBackupDict['morphemeBreak'] = self.morphemeBreak
        formBackupDict['morphemeGloss'] = self.morphemeGloss
        formBackupDict['grammaticality'] = self.grammaticality
        formBackupDict['comments'] = self.comments
        formBackupDict['speakerComments'] = self.speakerComments
        formBackupDict['dateElicited'] = self.dateElicited
        formBackupDict['datetimeEntered'] = self.datetimeEntered
        formBackupDict['datetimeModified'] = self.datetimeModified
        formBackupDict['syntacticCategoryString'] = self.syntacticCategoryString
        formBackupDict['morphemeBreakIDs'] = self.jsonLoads(self.morphemeBreakIDs)
        formBackupDict['morphemeGlossIDs'] = self.jsonLoads(self.morphemeGlossIDs)
        formBackupDict['breakGlossCategory'] = self.breakGlossCategory
        formBackupDict['elicitationMethod'] = self.jsonLoads(self.elicitationMethod)
        formBackupDict['syntacticCategory'] = self.jsonLoads(self.syntacticCategory)
        formBackupDict['source'] = self.jsonLoads(self.source)
        formBackupDict['speaker'] = self.jsonLoads(self.speaker)
        formBackupDict['elicitor'] = self.jsonLoads(self.elicitor)
        formBackupDict['enterer'] = self.jsonLoads(self.enterer)
        formBackupDict['verifier'] = self.jsonLoads(self.verifier)
        formBackupDict['backuper'] = self.jsonLoads(self.backuper)
        formBackupDict['glosses'] = self.jsonLoads(self.glosses)
        formBackupDict['tags'] = self.jsonLoads(self.tags)
        formBackupDict['files'] = self.jsonLoads(self.files)
        return formBackupDict

    def load(self):
        """Convert the JSON objects back into Column objects, thus making the
        FormBackup behave just like a Form object.  Almost.

        """

        if self.elicitationMethod:
            elicitationMethod = json.loads(self.elicitationMethod)
            self.elicitationMethod = self.Column()
            self.elicitationMethod.id = elicitationMethod['id']
            self.elicitationMethod.name = elicitationMethod['name']
        if self.syntacticCategory:
            syntacticCategory = json.loads(self.syntacticCategory)
            self.syntacticCategory = self.Column()
            self.syntacticCategory.id = syntacticCategory['id']
            self.syntacticCategory.name = syntacticCategory['name']
        if self.source:
            source = json.loads(self.source)
            self.source = self.Column()
            self.source.id = source['id']
            self.source.authorFirstName = source['authorFirstName']
            self.source.authorLastName = source['authorLastName']
            self.source.year = source['year']
            self.source.fullReference = source['fullReference']
        if self.speaker:
            speaker = json.loads(self.speaker)
            self.speaker = self.Column()
            self.speaker.id = speaker['id']
            self.speaker.firstName = speaker['firstName']
            self.speaker.lastName = speaker['lastName']
            self.speaker.dialect = speaker['dialect']
        if self.elicitor:
            elicitor = json.loads(self.elicitor)
            self.elicitor = self.Column()
            self.elicitor.id = elicitor['id']
            self.elicitor.firstName = elicitor['firstName']
            self.elicitor.lastName = elicitor['lastName']
        if self.enterer:
            enterer = json.loads(self.enterer)
            self.enterer = self.Column()
            self.enterer.id = enterer['id']
            self.enterer.firstName = enterer['firstName']
            self.enterer.lastName = enterer['lastName']
        if self.verifier:
            verifier = json.loads(self.verifier)
            self.verifier = self.Column()
            self.verifier.id = verifier['id']
            self.verifier.firstName = verifier['firstName']
            self.verifier.lastName = verifier['lastName']
        if self.glosses:
            glosses = json.loads(self.glosses)
            self.glosses = []
            for glossDict in glosses:
                gloss = self.Column()
                gloss.id = glossDict['id']
                gloss.gloss = glossDict['gloss']
                gloss.glossGrammaticality = glossDict['glossGrammaticality']
                self.glosses.append(gloss)
        if self.tags:
            tags = json.loads(self.tags)
            self.tags = []
            for tagDict in tags:
                tag = self.Column()
                tag.id = tagDict['id']
                tag.name = tagDict['name']
                self.tags.append(tag)
        if self.files:
            files = json.loads(self.files)
            self.files = []
            for fileDict in files:
                file = self.Column()
                file.id = fileDict['id']
                file.name = fileDict['name']
                file.embeddedFileMarkup = fileDict['embeddedFileMarkup']
                file.embeddedFilePassword = fileDict['embeddedFilePassword']
                self.files.append(file)
        if self.backuper:
            backuper = json.loads(self.backuper)
            self.backuper = self.Column()
            self.backuper.id = backuper['id']
            self.backuper.firstName = backuper['firstName']
            self.backuper.lastName = backuper['lastName']
