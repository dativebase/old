"""The application's model objects"""

from sqlalchemy import orm, schema, types
import simplejson as json
import datetime

from old.model import meta

def init_model(engine):
    """Call me before using any of the tables or classes in the model"""
    meta.engine = engine


def now():
    return datetime.datetime.utcnow()

################################################################################
# PRIMARY TABLES
################################################################################

# form_table holds the data that constitute OLD Forms
form_table = schema.Table('form', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('form_seq_id', optional=True), primary_key=True),
    schema.Column('UUID', types.Unicode(36)),
    # Textual values
    schema.Column('transcription', types.Unicode(255), nullable=False),
    schema.Column('phoneticTranscription', types.Unicode(255)),
    schema.Column('narrowPhoneticTranscription', types.Unicode(255)),
    schema.Column('morphemeBreak', types.Unicode(255)),
    schema.Column('morphemeGloss', types.Unicode(255)),
    schema.Column('comments', types.UnicodeText()),
    schema.Column('speakerComments', types.UnicodeText()), 
    # Forced choice textual values
    schema.Column('grammaticality', types.Unicode(255)),
    # Temporal values: only dateElicited is user-enterable.
    schema.Column('dateElicited', types.Date()),
    schema.Column('datetimeEntered', types.DateTime()),
    schema.Column('datetimeModified', types.DateTime(), default=now),
    # syntacticCategoryString: OLD-generated value 
    schema.Column('syntacticCategoryString', types.Unicode(255)),
    # morphemeBreakIDs and morphemeGlossIDs: OLD-generated values
    schema.Column('morphemeBreakIDs', types.UnicodeText()),
    schema.Column('morphemeGlossIDs', types.UnicodeText()),
    # breakGlossCategory: OLD-generated value, e.g., 'chien|dog|N-s|PL|NUM'
    schema.Column('breakGlossCategory', types.Unicode(1023)),
    schema.Column('syntax', types.Unicode(1023)),
    schema.Column('semantics', types.Unicode(1023)),
    # Many-to-One
    # A Form can have max one elicitor, enterer, verifier, speaker, elicitation
    # method, syntactic category and source.
    schema.Column('elicitor_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('enterer_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('verifier_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('speaker_id', types.Integer, schema.ForeignKey('speaker.id')),
    schema.Column('elicitationmethod_id', types.Integer,
                  schema.ForeignKey('elicitationmethod.id')),
    schema.Column('syntacticcategory_id', types.Integer,
                  schema.ForeignKey('syntacticcategory.id')),
    schema.Column('source_id', types.Integer, schema.ForeignKey('source.id'))

    # One-to-Many
    # Glosses - a Form can have many glosses

    # Many-to-Many
    # Tags - a Form can have many Tags and a Tag can have many Forms
    # Files - a Form can have many Files and a File can have many Forms:
)

# gloss_table holds the glosses for OLD Forms
gloss_table = schema.Table('gloss', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('gloss_seq_id', optional=True), primary_key=True),
    schema.Column('gloss', types.UnicodeText(), nullable=False),
    schema.Column('glossGrammaticality', types.Unicode(255)),

    # A Gloss can have only one Form, but a Form can have many Glosses.
    # Gloss-Form = Many-to-One
    schema.Column('form_id', types.Integer, schema.ForeignKey('form.id')),
    
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

# file_table holds the info about OLD Files (i.e., images, audio, video, PDFs) 
file_table = schema.Table('file', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('file_seq_id', optional=True), primary_key=True),

    schema.Column('name', types.Unicode(255), unique=True),
    schema.Column('MIMEtype', types.Unicode(255)),
    schema.Column('size', types.Integer),
    schema.Column('enterer_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('description', types.UnicodeText()),

    schema.Column('dateElicited', types.Date()),
    schema.Column('datetimeEntered', types.DateTime()),    
    schema.Column('datetimeModified', types.DateTime(), default=now),

    # A File can have only one each of elicitor or speaker but each 
    # of these can have more than one File
    schema.Column('elicitor_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('speaker_id', types.Integer, schema.ForeignKey('speaker.id')),

    # Utterance type: object lang only, metalang only, mixed, none
    schema.Column('utteranceType', types.Unicode(255)),

    # Fields used if the File is located on another server and its content is
    #  embedded in OLD
    schema.Column('embeddedFileMarkup', types.UnicodeText()),
    schema.Column('embeddedFilePassword', types.Unicode(255))
)

# collection_table holds info about OLD Collections: stories, discourses,
#  elicitations, ...
collection_table = schema.Table('collection', meta.metadata, 
    schema.Column('id', types.Integer,
        schema.Sequence('collection_seq_id', optional=True), primary_key=True),

    schema.Column('title', types.Unicode(255)),
    schema.Column('type', types.Unicode(255)),
    schema.Column('url', types.Unicode(255)),

    # Foreign key columns
    schema.Column('speaker_id', types.Integer, schema.ForeignKey('speaker.id')),
    schema.Column('source_id', types.Integer, schema.ForeignKey('source.id')),
    schema.Column('elicitor_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('enterer_id', types.Integer, schema.ForeignKey('user.id')),

    schema.Column('dateElicited', types.Date()),
    schema.Column('datetimeEntered', types.DateTime()),
    schema.Column('datetimeModified', types.DateTime(), default=now),

    schema.Column('description', types.UnicodeText()),
    schema.Column('contents', types.UnicodeText())
)

# user_table holds info about registered users
user_table = schema.Table('user', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('user_seq_id', optional=True), primary_key=True),

    schema.Column('username', types.Unicode(255), unique=True),
    schema.Column('password', types.Unicode(255)),
    schema.Column('firstName', types.Unicode(255)),
    schema.Column('lastName', types.Unicode(255)),
    schema.Column('email', types.Unicode(255)),
    schema.Column('affiliation', types.Unicode(255)),
    schema.Column('role', types.Unicode(255)),
    schema.Column('personalPageContent', types.UnicodeText()),
    schema.Column('collectionViewType', types.Unicode(255), default=u'long'),
    schema.Column('inputOrthography', types.Unicode(255)),
    schema.Column('outputOrthography', types.Unicode(255)),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

speaker_table = schema.Table('speaker', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('speaker_seq_id', optional=True), primary_key=True),
    schema.Column('firstName', types.Unicode(255)),
    schema.Column('lastName', types.Unicode(255)),
    schema.Column('dialect', types.Unicode(255)),
    schema.Column('speakerPageContent', types.UnicodeText()),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

syntacticcategory_table = schema.Table('syntacticcategory', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('syntacticcategory_seq_id', optional=True),
        primary_key=True),
    schema.Column('name', types.Unicode(255)),
    schema.Column('type', types.Unicode(60)),
    schema.Column('description', types.UnicodeText()),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

tag_table = schema.Table('tag', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('tag_seq_id', optional=True), primary_key=True),
    schema.Column('name', types.Unicode(255), unique=True),
    schema.Column('description', types.UnicodeText()),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

elicitationmethod_table = schema.Table('elicitationmethod', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('elicitationmethod_seq_id', optional=True),
        primary_key=True),
    schema.Column('name', types.Unicode(255)),
    schema.Column('description', types.UnicodeText()),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

source_table = schema.Table('source', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('source_seq_id', optional=True), primary_key=True),
    schema.Column('authorFirstName', types.Unicode(255)),
    schema.Column('authorLastName', types.Unicode(255)),
    schema.Column('title', types.Unicode(255)),
    schema.Column('year', types.Integer),
    schema.Column('fullReference', types.UnicodeText()),
    schema.Column('file_id', types.Integer, schema.ForeignKey('file.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

# applicationsettings_table holds the info about the settings of the application
applicationsettings_table = schema.Table('applicationsettings', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('applicationsettings_seq_id', optional=True),
        primary_key=True
    ),

    schema.Column('objectLanguageName', types.Unicode(255)),
    schema.Column('objectLanguageId', types.Unicode(3)),

    schema.Column('metalanguageName', types.Unicode(255)),
    schema.Column('metalanguageId', types.Unicode(3)),
    schema.Column('metalanguageInventory', types.UnicodeText()),

    schema.Column('orthographicValidation', types.Unicode(7)),

    schema.Column('narrowPhoneticInventory', types.UnicodeText()),
    schema.Column('narrowPhoneticValidation', types.Unicode(7)),

    schema.Column('broadPhoneticInventory', types.UnicodeText()),
    schema.Column('broadPhoneticValidation', types.Unicode(7)),

    schema.Column('morphemeBreakIsOrthographic', types.Boolean()),
    schema.Column('morphemeBreakValidation', types.Unicode(7)),
    schema.Column('phonemicInventory', types.UnicodeText()),
    schema.Column('morphemeDelimiters', types.Unicode(255)),

    schema.Column('punctuation', types.UnicodeText()),
    schema.Column('grammaticalities', types.Unicode(255)),

    schema.Column('storageOrthography_id', types.Integer,
                  schema.ForeignKey('orthography.id')),
    schema.Column('inputOrthography_id', types.Integer,
                  schema.ForeignKey('orthography.id')),
    schema.Column('outputOrthography_id', types.Integer,
                  schema.ForeignKey('orthography.id')),

    schema.Column('datetimeModified', types.DateTime(), default=now)

    # Many-to-Many relations:
    # - unrestrictedUsers
    # - orthographies

)

# orthography_table
orthography_table = schema.Table('orthography', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('orthography_seq_id', optional=True),
        primary_key=True
    ),
    schema.Column('name', types.Unicode(255)),
    schema.Column('orthography', types.UnicodeText()),
    schema.Column('lowercase', types.Boolean()),
    schema.Column('initialGlottalStops', types.Boolean()),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

# language_table holds ISO-639-3 data on the world's languages
#  - see http://www.sil.org/iso639-3/download.asp
#  - this table is populated from lib/languages/iso-639-3.tab
#    when "paster setup-app" is run
language_table = schema.Table('language', meta.metadata,
    schema.Column('Id', types.Unicode(3), primary_key=True),
    schema.Column('Part2B', types.Unicode(3)),
    schema.Column('Part2T', types.Unicode(3)),
    schema.Column('Part1', types.Unicode(2)),
    schema.Column('Scope', types.Unicode(1)),
    schema.Column('Type', types.Unicode(1)),
    schema.Column('Ref_Name', types.Unicode(150)),
    schema.Column('Comment', types.Unicode(150)),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

# page_table holds the text (markup) for user-generated pages 
page_table = schema.Table('page', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('page_seq_id', optional=True),
        primary_key=True
    ),
    schema.Column('name', types.Unicode(255)),
    schema.Column('content', types.UnicodeText()),
    schema.Column('html', types.UnicodeText()),
    schema.Column('heading', types.Unicode(255)),
    schema.Column('markup', types.Unicode(255)),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

# phonology_table holds the metadata for phonology FSTs
phonology_table = schema.Table('phonology', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('phonology_seq_id', optional=True),
        primary_key=True
    ),
    schema.Column('name', types.Unicode(255)),
    schema.Column('description', types.UnicodeText()),
    schema.Column('script', types.UnicodeText()),
    schema.Column('enterer_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('modifier_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('datetimeEntered', types.DateTime()),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

# formsearch_table holds the searches on OLD Forms
formsearch_table = schema.Table('formsearch', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('formsearch_seq_id', optional=True), primary_key=True),
    schema.Column('json', types.UnicodeText()),
    schema.Column('searcher_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

################################################################################
# RELATIONAL TABLES
################################################################################

"""formfile_table encodes the many-to-many relationship
between OLD Forms and OLD Files."""
formfile_table = schema.Table('formfile', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('formfile_seq_id', optional=True), primary_key=True),
    schema.Column('form_id', types.Integer, schema.ForeignKey('form.id')),
    schema.Column('file_id', types.Integer, schema.ForeignKey('file.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

"""formtag_table encodes the many-to-many relationship
between OLD Forms and OLD Tags."""
formtag_table = schema.Table('formtag', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('formfile_seq_id', optional=True), primary_key=True),
    schema.Column('form_id', types.Integer, schema.ForeignKey('form.id')),
    schema.Column('tag_id', types.Integer, schema.ForeignKey('tag.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)


collectionform_table = schema.Table('collectionform', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('collectionform_seq_id', optional=True), primary_key=True),
    schema.Column('collection_id', types.Integer, schema.ForeignKey('collection.id')),
    schema.Column('form_id', types.Integer, schema.ForeignKey('form.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

collectionfile_table = schema.Table('collectionfile', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('collectionfile_seq_id', optional=True), primary_key=True),
    schema.Column('collection_id', types.Integer, schema.ForeignKey('collection.id')),
    schema.Column('file_id', types.Integer, schema.ForeignKey('file.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

"""userform_table encodes the many-to-many relationship
between OLD Users and OLD Forms.  This is where the per-user
Memory is stored."""
userform_table = schema.Table('userform', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('userform_seq_id', optional=True), primary_key=True),
    schema.Column('form_id', types.Integer, schema.ForeignKey('form.id')),
    schema.Column('user_id', types.Integer, schema.ForeignKey('user.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

applicationsettingsorthography_table = schema.Table(
    'applicationsettingsorthography', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('applicationsettingsorthography_seq_id', optional=True),
        primary_key=True),
    schema.Column('applicationsettings_id', types.Integer,
                  schema.ForeignKey('applicationsettings.id')),
    schema.Column('orthography_id', types.Integer,
                  schema.ForeignKey('orthography.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)

applicationsettingsuser_table = schema.Table(
    'applicationsettingsuser', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('applicationsettingsuser_seq_id', optional=True),
        primary_key=True),
    schema.Column('applicationsettings_id', types.Integer,
                  schema.ForeignKey('applicationsettings.id')),
    schema.Column('user_id', types.Integer,
                  schema.ForeignKey('user.id')),
    schema.Column('datetimeModified', types.DateTime(), default=now)
)


################################################################################
# BACKUP TABLES
################################################################################

# formbackup_table is used to save form_table data that has been updated
#  or deleted.  This is a non-relational table, because keeping a copy of 
#  every single change seemed more work than it's worth.
formbackup_table = schema.Table('formbackup', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('formbackup_seq_id', optional=True), primary_key=True),
    # form_id is NOT a foreign key.  This is because (1) the form can be deleted,
    # (2) SQLite by default recycles the primary keys of deleted records, and
    # (3) I can't figure out how to turn off this default primary key recycling
    # via SQLAlchemy.  The UUID field links forms with their backups.
    schema.Column('form_id', types.Integer),
    schema.Column('UUID', types.Unicode(36)),
    schema.Column('transcription', types.Unicode(255), nullable=False),
    schema.Column('phoneticTranscription', types.Unicode(255)),
    schema.Column('narrowPhoneticTranscription', types.Unicode(255)),
    schema.Column('morphemeBreak', types.Unicode(255)),
    schema.Column('morphemeGloss', types.Unicode(255)),
    schema.Column('comments', types.UnicodeText()),
    schema.Column('speakerComments', types.UnicodeText()), 

    # Forced choice textual values
    schema.Column('grammaticality', types.Unicode(255)),

    # Temporal values: only dateElicited is non-mediately user-generated
    schema.Column('dateElicited', types.Date()),
    schema.Column('datetimeEntered', types.DateTime()),
    schema.Column('datetimeModified', types.DateTime(), default=now),

    # syntacticCategoryString: OLD-generated value 
    schema.Column('syntacticCategoryString', types.Unicode(255)),

    # morphemeBreakIDs and morphemeGlossIDs: OLD-generated values
    schema.Column('morphemeBreakIDs', types.UnicodeText()),
    schema.Column('morphemeGlossIDs', types.UnicodeText()),

    # breakGlossCategory: OLD-generated value, e.g., 'chien|dog|N-s|PL|NUM'
    schema.Column('breakGlossCategory', types.Unicode(1023)),

    # Previously Many-to-One
    schema.Column('elicitor', types.UnicodeText()),
    schema.Column('enterer', types.UnicodeText()),
    schema.Column('verifier', types.UnicodeText()),
    schema.Column('speaker', types.UnicodeText()),
    schema.Column('elicitationMethod', types.UnicodeText()),
    schema.Column('syntacticCategory', types.UnicodeText()),
    schema.Column('source', types.UnicodeText()),

    # Previously One-to-Many
    schema.Column('glosses', types.UnicodeText()),
    
    # Previously Many-to-Many
    schema.Column('tags', types.UnicodeText()),
    schema.Column('files', types.UnicodeText()), 

    schema.Column('backuper', types.UnicodeText())
)


# collectionbackup_table is used to save collection_table data that has been
#  updated or deleted.  Like formbackup_table, this table has no foreign keys.
collectionbackup_table = schema.Table('collectionbackup', meta.metadata,
    schema.Column('id', types.Integer,
        schema.Sequence('collectionbackup_seq_id', optional=True), primary_key=True),

    schema.Column('collection_id', types.Integer),
    schema.Column('title', types.Unicode(255)),
    schema.Column('type', types.Unicode(255)),
    schema.Column('url', types.Unicode(255)),
    schema.Column('description', types.UnicodeText()),
    schema.Column('contents', types.UnicodeText()),

    # Temporal values: only dateElicited is non-mediately user-generated
    schema.Column('dateElicited', types.Date()),
    schema.Column('datetimeEntered', types.DateTime()),
    schema.Column('datetimeModified', types.DateTime(), default=now),

    # Previously Many-to-One
    schema.Column('speaker', types.Unicode(255)),
    schema.Column('source', types.UnicodeText()),
    schema.Column('elicitor', types.Unicode(255)),
    schema.Column('enterer', types.Unicode(255)),

    schema.Column('backuper', types.Unicode(255)),
    schema.Column('files', types.UnicodeText())
)


################################################################################
# CLASSES
################################################################################


class Model(object):

    def getDictFromModel(self, model, attrs):
        dict_ = {}
        try:
            for attr in attrs:
                dict_[attr] = getattr(model, attr)
            return dict_
        except AttributeError:
            return None

    def jsonLoads(self, JSONString):
        try:
            return json.loads(JSONString)
        except (json.decoder.JSONDecodeError, TypeError):
            return None

    def getMiniUserDict(self, user):
        return self.getDictFromModel(user, ['id', 'firstName', 'lastName'])
    
    def getMiniSpeakerDict(self, speaker):
        return self.getDictFromModel(speaker, ['id', 'firstName', 'lastName',
                                               'dialect'])
    
    def getMiniElicitationMethodDict(self, elicitationMethod):
        return self.getDictFromModel(elicitationMethod, ['id', 'name'])
    
    def getMiniSyntacticCategoryDict(self, syntacticCategory):
        return self.getDictFromModel(syntacticCategory, ['id', 'name'])
    
    def getMiniSourceDict(self, source):
        return self.getDictFromModel(source, ['id', 'authorFirstName',
                                    'authorLastName', 'year', 'fullReference'])
    
    def getMiniGlossDict(self, gloss):
        return self.getDictFromModel(gloss, ['id', 'gloss', 'glossGrammaticality'])
    
    def getMiniTagDict(self, tag):
        return self.getDictFromModel(tag, ['id', 'name'])
    
    def getMiniFileDict(self, file):
        return self.getDictFromModel(file, ['id', 'name', 'embeddedFileMarkup',
                                       'embeddedFilePassword'])
    
    def getGlossesList(self, glosses):
        return [self.getMiniGlossDict(gloss) for gloss in glosses]
    
    def getTagsList(self, tags):
        return [self.getMiniTagDict(tag) for tag in tags]
    
    def getFilesList(self, files):
        return [self.getMiniFileDict(file) for file in files]

    class Column(object):
        """Empty class that can be used to convert JSON objects into Python
        ones.
        """
        pass

class Form(Model):
    """Class for creating OLD Form models."""

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

class FormBackup(Model):
    """Class for creating OLD FormBackup models.
    
    The dump method takes a Form and a User object as input and populates a
    number of Form-like attributes, converting relational attributes to JSON
    objects.
    
    The load method converts the JSON objects into Python Column objects, thus
    allowing the FormBackup to behave more like a Form object.
    """

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



class File(object):
    pass

class Collection(object):
    pass

class CollectionBackup(object):
    pass

class Phonology(object):
    pass

class Gloss(object):
    pass

class User(object):
    pass

class Speaker(object):
    pass

class ElicitationMethod(object):
    pass

class SyntacticCategory(object):
    pass

class Tag(object):
    pass

class Source(object):
    pass

class ApplicationSettings(object):
    pass

class Orthography(object):
    pass

class Language(object):
    pass

class Page(object):
    pass

class FormTag(object):
    pass

class FormFile(object):
    pass

class UserForm(object):
    pass

class FormSearch(object):
    pass

################################################################################
# MAPPPERS
################################################################################
  
orm.mapper(Form, form_table, properties={
    'speaker': orm.relation(Speaker),
    'elicitationMethod': orm.relation(ElicitationMethod),
    'syntacticCategory': orm.relation(SyntacticCategory),
    'elicitor': orm.relation(User, primaryjoin=(form_table.c.elicitor_id==user_table.c.id)),
    'enterer': orm.relation(User, primaryjoin=(form_table.c.enterer_id==user_table.c.id)),
    'verifier': orm.relation(User, primaryjoin=(form_table.c.verifier_id==user_table.c.id)),
    'source': orm.relation(Source),
    'glosses': orm.relation(Gloss, backref='form', cascade="all, delete, delete-orphan"),
    'files': orm.relation(File, secondary=formfile_table, backref='forms'),
    'collections': orm.relation(Collection, secondary=collectionform_table),
    'tags': orm.relation(Tag, secondary=formtag_table, backref='forms')
})
  
orm.mapper(Collection, collection_table, properties={
    'enterer': orm.relation(User, primaryjoin=(collection_table.c.enterer_id==user_table.c.id)),
    'elicitor': orm.relation(User, primaryjoin=(collection_table.c.elicitor_id==user_table.c.id)),
    'speaker': orm.relation(Speaker),
    'source': orm.relation(Source),
    'files':orm.relation(File, secondary=collectionfile_table),
    'forms':orm.relation(Form, secondary=collectionform_table)
})

orm.mapper(Gloss, gloss_table)

orm.mapper(File, file_table, properties={
    'enterer': orm.relation(User, primaryjoin=(file_table.c.enterer_id==user_table.c.id)),
    'elicitor': orm.relation(User, primaryjoin=(file_table.c.elicitor_id==user_table.c.id)),
    'speaker': orm.relation(Speaker)
})

orm.mapper(User, user_table, properties={
    'rememberedForms': orm.relation(Form, secondary=userform_table, backref='memorizers'),
})

orm.mapper(Speaker, speaker_table)

orm.mapper(SyntacticCategory, syntacticcategory_table)

orm.mapper(Tag, tag_table)

orm.mapper(ElicitationMethod, elicitationmethod_table)

orm.mapper(Source, source_table, properties={
    'file': orm.relation(File)
})

orm.mapper(FormBackup, formbackup_table)

orm.mapper(CollectionBackup, collectionbackup_table)

orm.mapper(ApplicationSettings, applicationsettings_table, properties={
    'storageOrthography': orm.relation(Orthography,
        primaryjoin=(
            applicationsettings_table.c.storageOrthography_id==orthography_table.c.id)),
    'inputOrthography': orm.relation(Orthography,
        primaryjoin=(
            applicationsettings_table.c.inputOrthography_id==orthography_table.c.id)),
    'outputOrthography': orm.relation(Orthography,
        primaryjoin=(
            applicationsettings_table.c.outputOrthography_id==orthography_table.c.id)),
    'orthographies': orm.relation(
        Orthography, secondary=applicationsettingsorthography_table),
    'unrestrictedUsers': orm.relation(
        User, secondary=applicationsettingsuser_table)
})

orm.mapper(Orthography, orthography_table)

orm.mapper(Language, language_table)

orm.mapper(Page, page_table)

orm.mapper(FormTag, formtag_table)

orm.mapper(FormFile, formfile_table)

orm.mapper(Phonology, phonology_table, properties={
    'enterer': orm.relation(
        User, primaryjoin=(phonology_table.c.enterer_id==user_table.c.id)),
    'modifier': orm.relation(
        User, primaryjoin=(phonology_table.c.modifier_id==user_table.c.id))
})

orm.mapper(UserForm, userform_table)

orm.mapper(FormSearch, formsearch_table, properties={
    'searcher': orm.relation(User,
                primaryjoin=(formsearch_table.c.searcher_id==user_table.c.id))
})