from formencode import variabledecode, All
from formencode.schema import Schema
from formencode.validators import Invalid, FancyValidator, Int, DateConverter, \
    UnicodeString, OneOf, Regex, Email, StringBoolean, String, URL
from formencode.foreach import ForEach
from formencode.api import NoDefault
import old.lib.helpers as h
from sqlalchemy.sql import and_
import old.lib.bibtex as bibtex
from pylons import app_globals
import old.model as model
from old.model.meta import Session
import logging
from base64 import b64decode
import os

log = logging.getLogger(__name__)


################################################################################
# Login Schemata
################################################################################

class LoginSchema(Schema):
    """LoginSchema validates that both username and password have been entered.""" 

    allow_extra_fields = True
    filter_extra_fields = True
    username = UnicodeString(not_empty=True)
    password = UnicodeString(not_empty=True)

class PasswordResetSchema(Schema):
    """PasswordResetSchema validates that a username has been submitted.""" 

    allow_extra_fields = True
    filter_extra_fields = True
    username = UnicodeString(not_empty=True)


################################################################################
# Form Schemata
################################################################################


class ValidGlosses(FancyValidator):
    """Validator for glosses.  Ensures that there is at least one non-empty
    gloss and that all glossGrammaticalities are valid.
    """

    messages = {
        'one_gloss': 'Please enter one or more glosses',
        'invalid_grammaticality': u''.join([u'At least one submitted gloss ',
                u'grammaticality does not match any of the available options.'])
    }

    def validate_python(self, value, state):
        try:
            glosses = [v['gloss'] for v in value if v['gloss'].strip()]
            glossGrammaticalities = [v['glossGrammaticality'] for v in value
                                     if v['glossGrammaticality'].strip()]
        except (AttributeError, KeyError, TypeError):
            glosses = []
            glossGrammaticalities = []
        validGrammaticalities = getGrammaticalities()
        badGlossGrammaticalities = [gg for gg in glossGrammaticalities
                                    if gg not in validGrammaticalities]
        if not glosses:
            raise Invalid(self.message("one_gloss", state), value, state)
        if badGlossGrammaticalities:
            raise Invalid(self.message("invalid_grammaticality", state), value, state)


class ValidOrthographicTranscription(UnicodeString):
    """Orthographic transcription validator.  If orthographic transcription
    validation is set to 'Error' in application settings, this validator will
    forbid orthographic transcriptions that are not constructable using the
    storage orthography and the specified punctuation.
    """

    messages = {u'invalid_transcription':
                u''.join([u'The orthographic transcription you have entered ',
                          u'is not valid. Only graphemes from the specified ',
                          u'storage orthography, punctuation characters and ',
                          u'the space character are permitted.'])}

    def validate_python(self, value, state):
        transcription = h.toSingleSpace(h.normalize(value))
        if not formIsForeignWord(state.full_dict) and \
        not transcriptionIsValid(transcription, 'orthographicValidation',
                                 'orthographicInventory'):
            raise Invalid(self.message("invalid_transcription", state),
                          value, state)


class ValidNarrowPhoneticTranscription(UnicodeString):
    """Narrow phonetic transcription validator.  If narrow phonetic
    transcription validation is set to 'Error' in application settings, this
    validator will forbid narrow phonetic transcriptions that are not
    constructable using the narrow phonetic inventory.
    """

    messages = {u'invalid_transcription':
                u''.join([u'The narrow phonetic transcription you have entered ',
                          u'is not valid. Only graphemes from the specified ',
                          u'narrow phonetic inventory and ',
                          u'the space character are permitted.'])}

    def validate_python(self, value, state):
        transcription = h.toSingleSpace(h.normalize(value))
        if not formIsForeignWord(state.full_dict) and \
        not transcriptionIsValid(transcription, 'narrowPhoneticValidation',
                                 'narrowPhoneticInventory'):
            raise Invalid(self.message("invalid_transcription", state),
                          value, state)


class ValidBroadPhoneticTranscription(UnicodeString):
    """Broad phonetic transcription validator.  If broad phonetic
    transcription validation is set to 'Error' in application settings, this
    validator will forbid broad phonetic transcriptions that are not
    constructable using the broad phonetic inventory.
    """

    messages = {u'invalid_transcription':
                u''.join([u'The broad phonetic transcription you have entered ',
                          u'is not valid. Only graphemes from the specified ',
                          u'broad phonetic inventory and ',
                          u'the space character are permitted.'])}

    def validate_python(self, value, state):
        transcription = h.toSingleSpace(h.normalize(value))
        if not formIsForeignWord(state.full_dict) and \
        not transcriptionIsValid(transcription, 'broadPhoneticValidation',
                                 'broadPhoneticInventory'):
            raise Invalid(self.message("invalid_transcription", state),
                          value, state)


class ValidMorphemeBreakTranscription(UnicodeString):
    """Morpheme break input validator.  If morpheme break validation is set to
    'Error' in application settings, this validator will forbid morpheme break
    input that is not constructable using the relevant grapheme inventory (i.e.,
    either the storage orthography or the phonemic inventory) and the specified
    morpheme delimiters.
    """

    messages = {u'invalid_transcription':
                u''.join([u'The morpheme segmentation you have entered ',
                          u'is not valid.  Only graphemes from the ',
                          u'%(inventory)s, the specified morpheme delimiters ',
                          u'and the space character are permitted.'])}

    def validate_python(self, value, state):
        transcription = h.toSingleSpace(h.normalize(value))
        try:
            morphemeBreakIsOrthographic = getattr(getattr(getattr(
                app_globals, 'applicationSettings', None),
                'applicationSettings', None),
                'morphemeBreakIsOrthographic', False)
        except TypeError:
            morphemeBreakIsOrthographic = False
        inventory = u'phonemic inventory'
        if morphemeBreakIsOrthographic:
            inventory = u'storage orthography'
        if not formIsForeignWord(state.full_dict) and \
        not transcriptionIsValid(transcription, 'morphemeBreakValidation',
                                 'morphemeBreakInventory'):
            raise Invalid(self.message("invalid_transcription", state,
                inventory=inventory), value, state)


def formIsForeignWord(formDict):
    """Returns False if the form being entered (as represented by the formDict)
    is tagged as a foreign word; otherwise return True.
    """

    tagIds = [h.getInt(id) for id in formDict.get('tags', [])]
    tagIds = [id for id in tagIds if id]
    try:
        foreignWordTagId = h.getForeignWordTag().id
    except AttributeError:
        foreignWordTagId = None
    if foreignWordTagId in tagIds:
        return True
    return False


def transcriptionIsValid(transcription, validationName, inventoryName):
    """Returns a boolean indicating whether the transcription is valid according
    to the appropriate Inventory object in the Application Settings meta object.
    The validationName parameter is the name of the appropriate validation
    attribute of the application settings model object, e.g.,
    'orthographicValidation'.  The inventoryName parameter is the name of an
    attribute of the Application Settings meta object whose value is the
    appropriate Inventory object for the transcription.
    """

    if getattr(getattr(getattr(app_globals, 'applicationSettings', None),
    'applicationSettings', None), validationName, None) == u'Error':
        return getattr(getattr(app_globals, 'applicationSettings', None),
            inventoryName, None).stringIsValid(transcription)
    return True


class ValidGrammaticality(FancyValidator):

    messages = {u'invalid_grammaticality':
        u'The grammaticality submitted does not match any of the available options.'}

    def validate_python(self, value, state):
        validGrammaticalities = getGrammaticalities()
        if value not in validGrammaticalities:
            raise Invalid(self.message("invalid_grammaticality", state),
                          value, state)


def getGrammaticalities():
    try:
        grammaticalities = getattr(getattr(
            app_globals, 'applicationSettings', None), 'grammaticalities', [u''])
    except TypeError, e:
        # During testing, app_globals may not be present.
        grammaticalities = [u'']
    return grammaticalities


class ValidOLDModelObject(FancyValidator):
    """Validator for input values that are integer ids (i.e., primary keys) of
    OLD model objects.  Value must be int-able as well as the id of an existing
    OLD of the type specified in the modelName kwarg.  If valid, the model
    object is returned.  Example usage: ValidOLDModelObject(modelName='User').
    """

    messages = {
        'invalid_model': u'There is no %(modelNameEng)s with id %(id)d.',
        'restricted_model':
            u'You are not authorized to access the %(modelNameEng)s with id %(id)d.'
    }

    def _to_python(self, value, state):
        if value in [u'', None]:
            return None
        else:
            id = Int().to_python(value, state)
            modelObject = Session.query(getattr(model, self.modelName)).get(id)
            if modelObject is None:
                raise Invalid(self.message("invalid_model", state, id=id,
                    modelNameEng=h.camelCase2lowerSpace(self.modelName)),
                    value, state)
            else:
                if self.modelName in ('Form', 'File', 'Collection') and \
                getattr(state, 'user', None):
                    unrestrictedUsers = h.getUnrestrictedUsers()
                    if h.userIsAuthorizedToAccessModel(state.user, modelObject, unrestrictedUsers):
                        return modelObject
                    else:
                        raise Invalid(self.message("restricted_model", state, id=id,
                            modelNameEng=h.camelCase2lowerSpace(self.modelName)),
                            value, state)
                else:
                    return modelObject


class FormSchema(Schema):
    """FormSchema is a Schema for validating the data input upon a form
    creation request.
    """
    allow_extra_fields = True
    filter_extra_fields = True

    transcription = ValidOrthographicTranscription(not_empty=True, max=255)
    phoneticTranscription = ValidBroadPhoneticTranscription(max=255)
    narrowPhoneticTranscription = ValidNarrowPhoneticTranscription(max=255)
    morphemeBreak = ValidMorphemeBreakTranscription(max=255)
    grammaticality = ValidGrammaticality()
    morphemeGloss = UnicodeString(max=255)
    glosses = ValidGlosses(not_empty=True)
    comments = UnicodeString()
    speakerComments = UnicodeString()
    elicitationMethod = ValidOLDModelObject(modelName='ElicitationMethod')
    syntacticCategory = ValidOLDModelObject(modelName='SyntacticCategory')
    speaker = ValidOLDModelObject(modelName='Speaker')
    elicitor = ValidOLDModelObject(modelName='User')
    verifier = ValidOLDModelObject(modelName='User')
    source = ValidOLDModelObject(modelName='Source')
    tags = ForEach(ValidOLDModelObject(modelName='Tag'))
    files = ForEach(ValidOLDModelObject(modelName='File'))
    dateElicited = DateConverter(month_style='mm/dd/yyyy')


class FormIdsSchema(Schema):
    allow_extra_fields = True
    filter_extra_fields = True
    forms = ForEach(ValidOLDModelObject(modelName='Form'), not_empty=True)


################################################################################
# File Schemata
################################################################################

class ValidBase64EncodedFile(String):
    """Validator for the 'file' attribute of a file create request."""

    messages = {u'invalid_base64_encoded_file':
                u'The uploaded file must be base64 encoded.'}

    def _to_python(self, value, state):
        try:
            return b64decode(value)
        except (TypeError, UnicodeEncodeError):
            raise Invalid(self.message('invalid_base64_encoded_file', state), value, state)

class ValidFileName(UnicodeString):
    """Ensures that the filename of the file to be uploaded has a valid extension
    given the allowed file types listed in lib/utils.py.
    """

    messages = {u'invalid_file_name':
                u'The file upload failed because the file type is not allowed.'}

    def _to_python(self, value, state):
        if h.guess_type(value)[0] in h.allowedFileTypes:
            return value.replace(os.sep, '_').replace("'", "").replace(
                '"', '').replace(' ', '_')
        else:
            raise Invalid(self.message('invalid_file_name', state), value, state)

class FileUpdateSchema(Schema):
    """FileUpdateSchema is a Schema for validating the data input upon a file
    update request.
    """
    allow_extra_fields = True
    filter_extra_fields = True

    description = UnicodeString()
    utteranceType = OneOf(h.utteranceTypes)
    embeddedFileMarkup = UnicodeString()
    embeddedFilePassword = UnicodeString(max=255)
    speaker = ValidOLDModelObject(modelName='Speaker')
    elicitor = ValidOLDModelObject(modelName='User')
    tags = ForEach(ValidOLDModelObject(modelName='Tag'))
    forms = ForEach(ValidOLDModelObject(modelName='Form'))
    dateElicited = DateConverter(month_style='mm/dd/yyyy')

class FileCreateSchema(FileUpdateSchema):
    """FileCreateSchema is a Schema for validating the data input upon a file
    create request.  The file data and name can only be specified on the create
    request.
    """
    file = ValidBase64EncodedFile(not_empty=True)
    name = ValidFileName(not_empty=True, max=255)


################################################################################
# Collection Schemata
################################################################################

class CollectionSchema(Schema):
    """CollectionSchema is a Schema for validating the data input upon
    collection create and update requests.
    """
    allow_extra_fields = True
    filter_extra_fields = True

    title = UnicodeString(max=255, not_empty=True)
    type = OneOf(h.collectionTypes)
    url = Regex('^[a-zA-Z0-9_/-]{0,255}$')
    description = UnicodeString()
    markupLanguage = OneOf(h.markupLanguages)
    contents = UnicodeString()
    # html = UnicodeString()      # uncomment to permit saving of client-side-generated html
    speaker = ValidOLDModelObject(modelName='Speaker')
    source = ValidOLDModelObject(modelName='Source')
    elicitor = ValidOLDModelObject(modelName='User')
    enterer = ValidOLDModelObject(modelName='User')
    dateElicited = DateConverter(month_style='mm/dd/yyyy')
    tags = ForEach(ValidOLDModelObject(modelName='Tag'))
    files = ForEach(ValidOLDModelObject(modelName='File'))

    # A forms attribute must be created using the contents attribute before validation occurs
    forms = ForEach(ValidOLDModelObject(modelName='Form'))

################################################################################
# ApplicationSettings Schemata
################################################################################

class ApplicationSettingsSchema(Schema):
    """ApplicationSettingsSchema is a Schema for validating the data
    submitted to ApplicationsettingsController
    (controllers/applicationsettings.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True

    validationValues = [u'None', u'Warning', u'Error']
    objectLanguageName = UnicodeString(max=255)
    objectLanguageId = UnicodeString(max=3)
    metalanguageName = UnicodeString(max=255)
    metalanguageId = UnicodeString(max=3)
    metalanguageInventory = UnicodeString()
    orthographicValidation = OneOf(validationValues)
    narrowPhoneticInventory = UnicodeString()
    narrowPhoneticValidation = OneOf(validationValues)
    broadPhoneticInventory = UnicodeString()
    broadPhoneticValidation = OneOf(validationValues)
    morphemeBreakIsOrthographic = StringBoolean()
    morphemeBreakValidation = OneOf(validationValues)
    phonemicInventory = UnicodeString()
    morphemeDelimiters = UnicodeString(max=255)
    punctuation = UnicodeString()
    grammaticalities = UnicodeString(max=255)
    unrestrictedUsers = ForEach(Int())
    orthographies = ForEach(Int())
    storageOrthography = Int()
    inputOrthography = Int()
    outputOrthography = Int()


################################################################################
# Orthography Schemata
################################################################################

class OrthographySchema(Schema):
    """OrthographySchema is a Schema for validating the data submitted to
    OrthographyController (controllers/orthography.py).
    """

    allow_extra_fields = True
    filter_extra_fields = True

    name = UnicodeString(max=255)
    orthography = UnicodeString()
    lowercase = StringBoolean()
    initialGlottalStops = StringBoolean()


################################################################################
# Source Schemata
################################################################################

class ValidBibTeXEntryType(FancyValidator):
    """Validator for the source model's type field.  Value must be any case
    permutation of BibTeX entry types (cf. bibtex.entryTypes).  The value is
    returned all lowercase.
    """

    messages = {'invalid_bibtex_entry':
        '%(submittedEntry)s is not a valid BibTeX entry type'}

    def _to_python(self, value, state):
        if value.lower() in bibtex.entryTypes.keys():
            return value.lower()
        else:
            raise Invalid(self.message('invalid_bibtex_entry', state, submittedEntry=value),
                          value, state)

class ValidBibTexKey(FancyValidator):
    """Validator for the source model's key field.  Value must be any unique
    combination of ASCII letters, numerals and symbols (except the comma).
    """

    messages = {
        'invalid_bibtex_key_format': 'Source keys can only contain letters, numerals and symbols (except the comma)',
        'bibtex_key_not_unique': 'The submitted source key is not unique'
    }

    def validate_python(self, value, state):
        valid = '''0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+-./:;<=>?@[\\]^_`{|}~'''
        if set(list(value)) - set(list(valid)):
            raise Invalid(self.message('invalid_bibtex_key_format', state),
                          value, state)
        id = getattr(state, 'id', None)
        query = Session.query(model.Source)
        if (id and query.filter(and_(model.Source.key==value, model.Source.id!=id)).first()) or \
        (not id and query.filter(model.Source.key==value).first()):
            raise Invalid(self.message('bibtex_key_not_unique', state), value, state)

class ValidBibTeXEntry(FancyValidator):
    """Validator for a Source/BibTeX entry based on its type.  This validator is
    run as a formencode "chained validator", i.e., it is run after the validation
    and conversion of the type and key attributes.  It uses the information in
    lib/bibtex.entryTypes[type]['required'] to determine which attributes are
    required for which types.
    """

    messages = {'invalid_entry': '%(msg)s'}

    def parseRequirements(self, entryType):
        """Given a BibTeX entry type, return a tuple (a, b, c) where a is the
        list of required fields, b is the list of disjunctively required fields
        and c is a string expressing the requirements in English.
        """

        def coordinate(list_):
            if len(list_) > 1:
                return u'%s and %s' % (u', '.join(list_[:-1]), list_[-1])
            elif len(list_) == 1:
                return list_[0]
            return u''
        def conjugateValues(requiredFields):
            if len(requiredFields) > 1:
                return 'values'
            return 'a value'

        required = bibtex.entryTypes.get(entryType, {}).get('required', [])
        requiredFields = [r for r in required if isinstance(r, str)]
        disjunctivelyRequiredFields = [r for r in required if isinstance(r, tuple)]
        msg = u'Sources of type %s require %s for %s' % (
            entryType, conjugateValues(requiredFields), coordinate(requiredFields))
        if disjunctivelyRequiredFields:
            msg = u'%s as well as a value for %s' % (msg, 
                coordinate([u'at least one of %s' % coordinate(dr)
                            for dr in disjunctivelyRequiredFields]))
        return requiredFields, disjunctivelyRequiredFields, u'%s.' % msg

    def validate_python(self, values, state):
        invalid = False
        type = values.get('type', '')
        requiredFields, disjunctivelyRequiredFields, msg = self.parseRequirements(type)
        requiredFieldsValues = [values.get(rf) for rf in requiredFields if values.get(rf)]
        if len(requiredFieldsValues) != len(requiredFields):
            invalid = True
        else:
            for dr in disjunctivelyRequiredFields:
                drValues = [values.get(rf) for rf in dr if values.get(rf)]
                if not drValues:
                    invalid = True
        if invalid:
            raise Invalid(self.message('invalid_entry', state, msg=msg), values, state)

class SourceSchema(Schema):
    """SourceSchema is a Schema for validating the data submitted to
    SourceController (controllers/source.py).
    """

    allow_extra_fields = True
    filter_extra_fields = False
    chained_validators = [ValidBibTeXEntry()]

    type = ValidBibTeXEntryType(not_empty=True)   # OneOf lib.bibtex.entryTypes with any uppercase permutations
    key = ValidBibTexKey(not_empty=True, unique=True)  # any combination of letters, numerals and symbols (except commas)

    file = ValidOLDModelObject(modelName='File')

    address = UnicodeString(max=1000)
    annote = UnicodeString()
    author = UnicodeString(max=255)
    booktitle = UnicodeString(max=255)
    chapter = UnicodeString(max=255)
    crossref = UnicodeString(max=255)
    edition = UnicodeString(max=255)
    editor = UnicodeString(max=255)
    howpublished = UnicodeString(max=255)
    institution = UnicodeString(max=255)
    journal = UnicodeString(max=255)
    keyField = UnicodeString(max=255)
    month = UnicodeString(max=100)
    note = UnicodeString(max=1000)
    number = UnicodeString(max=100)
    organization = UnicodeString(max=255)
    pages = UnicodeString(max=100)
    publisher = UnicodeString(max=255)
    school = UnicodeString(max=255)
    series = UnicodeString(max=255)
    title = UnicodeString(max=255)
    typeField = UnicodeString(max=255)
    url = URL(add_http=True, max=1000)
    volume = UnicodeString(max=100)
    year = Int(min=-8000, max=3000) # The dawn of recorded history to a millenium into the future!

    # Non-standard BibTeX fields
    affiliation = UnicodeString(max=255)
    abstract = UnicodeString(max=1000)
    contents = UnicodeString(max=255)
    copyright = UnicodeString(max=255)
    ISBN = UnicodeString(max=20)
    ISSN = UnicodeString(max=20)
    keywords = UnicodeString(max=255)
    language = UnicodeString(max=255)
    location = UnicodeString(max=255)
    LCCN = UnicodeString(max=20)
    mrnumber = UnicodeString(max=25)
    price = UnicodeString(max=100)
    size = UnicodeString(max=255)
