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

"""FormBackup model

Used to save Form data that has been updated or deleted.  This is a
non-relational table, because keeping a copy of every single change relationally
seemed like more trouble than it's worth.
"""

from sqlalchemy import Table, Column, Sequence, ForeignKey
from sqlalchemy.types import Integer, Unicode, UnicodeText, Date, DateTime
from sqlalchemy.orm import relation, backref
from onlinelinguisticdatabase.model.meta import Base, now
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
    translations = Column(UnicodeText)
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
        self.translations = unicode(json.dumps(formDict['translations']))
        self.tags = unicode(json.dumps(formDict['tags']))
        self.files = unicode(json.dumps(formDict['files']))

    def getDict(self):
        return {
            'id': self.id,
            'UUID': self.UUID,
            'form_id': self.form_id,
            'transcription': self.transcription,
            'phoneticTranscription': self.phoneticTranscription,
            'narrowPhoneticTranscription': self.narrowPhoneticTranscription,
            'morphemeBreak': self.morphemeBreak,
            'morphemeGloss': self.morphemeGloss,
            'grammaticality': self.grammaticality,
            'comments': self.comments,
            'speakerComments': self.speakerComments,
            'dateElicited': self.dateElicited,
            'datetimeEntered': self.datetimeEntered,
            'datetimeModified': self.datetimeModified,
            'syntacticCategoryString': self.syntacticCategoryString,
            'morphemeBreakIDs': self.jsonLoads(self.morphemeBreakIDs),
            'morphemeGlossIDs': self.jsonLoads(self.morphemeGlossIDs),
            'breakGlossCategory': self.breakGlossCategory,
            'elicitationMethod': self.jsonLoads(self.elicitationMethod),
            'syntacticCategory': self.jsonLoads(self.syntacticCategory),
            'source': self.jsonLoads(self.source),
            'speaker': self.jsonLoads(self.speaker),
            'elicitor': self.jsonLoads(self.elicitor),
            'enterer': self.jsonLoads(self.enterer),
            'verifier': self.jsonLoads(self.verifier),
            'backuper': self.jsonLoads(self.backuper),
            'translations': self.jsonLoads(self.translations),
            'tags': self.jsonLoads(self.tags),
            'files': self.jsonLoads(self.files)
        }

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
        if self.translations:
            translations = json.loads(self.translations)
            self.translations = []
            for translationDict in translations:
                translation = self.Column()
                translation.id = translationDict['id']
                translation.transcription = translationDict['transcription']
                translation.grammaticality = translationDict['grammaticality']
                self.translations.append(translation)
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
