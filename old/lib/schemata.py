from formencode import All
from formencode.variabledecode import NestedVariables
from formencode.schema import Schema
from formencode.validators import Invalid, FancyValidator, Int, DateConverter, \
    UnicodeString, OneOf, Regex, Email, StringBoolean, String, URL, Number
from formencode.foreach import ForEach
from formencode.api import NoDefault
from old.lib.SQLAQueryBuilder import SQLAQueryBuilder, OLDSearchParseError
import old.lib.helpers as h
from sqlalchemy.sql import and_
import old.lib.bibtex as bibtex
from pylons import app_globals
import old.model as model
from old.model.meta import Session
import logging
from base64 import b64decode
import os, re
import simplejson as json
try:
    from magic import Magic
except ImportError:
    pass

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

    def _to_python(self, value, state):
        def createGloss(dict_):
            gloss = model.Gloss()
            gloss.gloss = h.toSingleSpace(h.normalize(dict_['gloss']))
            gloss.glossGrammaticality = dict_['glossGrammaticality']
            return gloss
        try:
            glosses = [g for g in value if g['gloss'].strip()]
            glossGrammaticalities = [g['glossGrammaticality'] for g in value
                                     if g['glossGrammaticality'].strip()]
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
        return [createGloss(g) for g in glosses]


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
    status = OneOf(h.formStatuses)
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
    """Schema used to validate a JSON object of the form {'forms': [1, 2, 3]}
    where value['forms'] can NOT be an empty array.  Used in the remember method
    of controllers.forms.
    """
    allow_extra_fields = True
    filter_extra_fields = True
    forms = ForEach(ValidOLDModelObject(modelName='Form'), not_empty=True)


class FormIdsSchemaNullable(Schema):
    """Schema used to validate a JSON object of the form {'forms': [1, 2, 3]}
    where value['forms'] can be an empty array.  Used in the update method of
    controllers.rememberedforms.
    """
    allow_extra_fields = True
    filter_extra_fields = True
    forms = ForEach(ValidOLDModelObject(modelName='Form'))

################################################################################
# File Schemata
################################################################################

def getMIMEtypeFromContents(contents):
    return Magic(mime=True).from_buffer(contents).replace('application/ogg', 'audio/ogg')

class ValidBase64EncodedFile(String):
    """Validator for the base64EncodedFile attribute of a file create request."""

    messages = {
        'invalid_base64_encoded_file': u'The uploaded file must be base64 encoded.'
    }
    def _to_python(self, value, state):
        try:
            return b64decode(value)
        except (TypeError, UnicodeEncodeError):
            raise Invalid(self.message('invalid_base64_encoded_file', state), value, state)

class ValidFileName(UnicodeString):
    """Ensures that the filename of the file to be uploaded has a valid extension
    given the allowed file types listed in lib/utils.py.  The 
    """

    messages = {u'invalid_type':
                u'The file upload failed because the file type %(MIMEtype)s is not allowed.'}

    def _to_python(self, value, state):
        MIMEtypeFromExt = h.guess_type(value)[0]
        if MIMEtypeFromExt in h.allowedFileTypes:
            return h.cleanAndSecureFilename(value)
        else:
            raise Invalid(self.message('invalid_type', state, MIMEtype=MIMEtypeFromExt), value, state)

class FileUpdateSchema(Schema):
    """FileUpdateSchema is a Schema for validating the data input upon a file
    update request.
    """
    allow_extra_fields = True
    filter_extra_fields = True
    description = UnicodeString()
    utteranceType = OneOf(h.utteranceTypes)
    speaker = ValidOLDModelObject(modelName='Speaker')
    elicitor = ValidOLDModelObject(modelName='User')
    tags = ForEach(ValidOLDModelObject(modelName='Tag'))
    forms = ForEach(ValidOLDModelObject(modelName='Form'))
    dateElicited = DateConverter(month_style='mm/dd/yyyy')

class AddMIMEtypeToValues(FancyValidator):
    """Guesses the MIMEtype based on the file contents and name and sets the
    MIMEtype key in values.  If python-magic is installed, the system will guess
    the type from the file contents and an error will be raised if the filename
    extension is inaccurate.
    """
    messages = {
        'mismatched_type': u'The file extension does not match the file\'s true type (%(x)s vs. %(y)s, respectively).'
    }
    def _to_python(self, values, state):
        MIMEtypeFromFilename = h.guess_type(values['filename'])[0]
        if 'base64EncodedFile' in values:
            contents = values['base64EncodedFile'][:1024]
        else:
            contents = values['filedataFirstKB']
        try:
            MIMEtypeFromContents = getMIMEtypeFromContents(contents)
            if MIMEtypeFromContents != MIMEtypeFromFilename:
                raise Invalid(self.message('mismatched_type', state,
                    x=MIMEtypeFromFilename, y=MIMEtypeFromContents), values, state)
        except (NameError, KeyError):
            pass    # NameError because Magic is not installed; KeyError because PlainFile validation will lack a base64EncodedFile key
        values['MIMEtype'] = unicode(MIMEtypeFromFilename)
        return values

class FileCreateWithBase64EncodedFiledataSchema(FileUpdateSchema):
    """Schema for validating the data input upon a file create request where a
    base64EncodedFile attribute is present in the JSON request params.  The
    base64EncodedFile and filename attributes can only be specified on the create
    request (i.e., not on the update request).
    """
    chained_validators = [AddMIMEtypeToValues()]
    base64EncodedFile = ValidBase64EncodedFile(not_empty=True)
    filename = ValidFileName(not_empty=True, max=255)
    MIMEtype = UnicodeString()

class FileCreateWithFiledataSchema(Schema):
    """Schema for validating the data input upon a file create request where the
    Content-Type is 'multipart/form-data'.

    Note the pre-validation NestedVariables call.  This causes certain key-value
    patterns to be transformed to Python data structures.  In this case,

        {'forms-0': 1, 'forms-1': 33, 'tags-0': 2, 'tags-1': 4, 'tags-2': 5}

    becomes

        {'forms': [1, 33], 'tags': [2, 4, 5]}
    """
    allow_extra_fields = True
    filter_extra_fields = True
    pre_validators = [NestedVariables()]
    chained_validators = [AddMIMEtypeToValues()]
    filename = ValidFileName(not_empty=True, max=255)
    filedataFirstKB = String()
    description = UnicodeString()
    utteranceType = OneOf(h.utteranceTypes)
    speaker = ValidOLDModelObject(modelName='Speaker')
    elicitor = ValidOLDModelObject(modelName='User')
    tags = ForEach(ValidOLDModelObject(modelName='Tag'))
    forms = ForEach(ValidOLDModelObject(modelName='Form'))
    dateElicited = DateConverter(month_style='mm/dd/yyyy')

class ValidAudioVideoFile(FancyValidator):
    """Validator for input values that are integer ids (i.e., primary keys) of
    OLD File objects representing audio or video files.  Note that the referenced
    A/V file must *not* itself be a subinterval-referencing file.
    """

    messages = {
        'invalid_file': u'There is no file with id %(id)d.',
        'restricted_file': u'You are not authorized to access the file with id %(id)d.',
        'not_av': u'File %(id)d is not an audio or a video file.',
        'empty': u'An id corresponding to an existing audio or video file must be provided.',
        'ref_ref': u'The parent file cannot itself be a subinterval-referencing file.'
    }

    def _to_python(self, value, state):
        if value in [u'', None]:
            raise Invalid(self.message('empty', state), value, state)
        else:
            id = Int().to_python(value, state)
            fileObject = Session.query(model.File).get(id)
            if fileObject is None:
                raise Invalid(self.message("invalid_file", state, id=id), value, state)
            else:
                if h.isAudioVideoFile(fileObject):
                    if fileObject.parentFile is None:
                        unrestrictedUsers = h.getUnrestrictedUsers()
                        if h.userIsAuthorizedToAccessModel(state.user, fileObject, unrestrictedUsers):
                            return fileObject
                        else:
                            raise Invalid(self.message("restricted_file", state, id=id),
                                          value, state)
                    else:
                        raise Invalid(self.message('ref_ref', state, id=id), value, state)
                else:
                    raise Invalid(self.message('not_av', state, id=id), value, state)

class ValidSubinterval(FancyValidator):
    """Validator ensures that the float/int value of the 'start' key is less
    than the float/int value of the 'end' key.  These values are also converted
    to floats.
    """
    messages = {
        'invalid': u'The start value must be less than the end value.',
        'not_numbers': u'The start and end values must be numbers.'
    }
    def _to_python(self, values, state):
        if type(values['start']) not in (int, float) or \
        type(values['end']) not in (int, float):
            raise Invalid(self.message('not_numbers', state), values, state)
        values['start'] == float(values['start'])
        values['end'] == float(values['end'])
        if values['start'] < values['end']:
            return values
        else:
            raise Invalid(self.message('invalid', state), values, state)

class FileSubintervalReferencingSchema(FileUpdateSchema):
    """Validates input for subinterval-referencing file creation and update
    requests.
    """
    chained_validators = [ValidSubinterval()]
    name = UnicodeString(max=255)
    parentFile = ValidAudioVideoFile(not_empty=True)
    start = Number(not_empty=True)
    end = Number(not_empty=True)

class ValidMIMEtype(FancyValidator):
    """Validator ensures that the user-supplied MIMEtype value is one of those
    listed in hallowedFileTypes.
    """
    messages = {u'invalid_type': u'The file upload failed because the file type %(MIMEtype)s is not allowed.'}
    def validate_python(self, value, state):
        if value not in h.allowedFileTypes:
            raise Invalid(self.message('invalid_type', state, MIMEtype=value), value, state)

class FileExternallyHostedSchema(FileUpdateSchema):
    """Validates input for files whose content is hosted elsewhere."""
    name = UnicodeString(max=255)
    url = URL(not_empty=True, check_exists=False, add_http=True)       # add check_exists=True if desired
    password = UnicodeString(max=255)
    MIMEtype = ValidMIMEtype()

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
    contentsUnpacked = UnicodeString()
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

class GetMorphemeDelimiters(FancyValidator):
    """Remove redundant commas and whitespace from the string representing the
    morpheme delimiters.
    """
    def _to_python(self, value, state):
        value = h.removeAllWhiteSpace(value)
        return ','.join([d for d in value.split(',') if d])

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
    morphemeDelimiters = GetMorphemeDelimiters(max=255)
    punctuation = UnicodeString()
    grammaticalities = UnicodeString(max=255)
    unrestrictedUsers = ForEach(ValidOLDModelObject(modelName='User'))
    orthographies = ForEach(ValidOLDModelObject(modelName='Orthography'))
    storageOrthography = ValidOLDModelObject(modelName='Orthography')
    inputOrthography = ValidOLDModelObject(modelName='Orthography')
    outputOrthography = ValidOLDModelObject(modelName='Orthography')


################################################################################
# Source Validators
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
    combination of ASCII letters, numerals and symbols (except the comma).  The
    presence of an 'id' attribute on the state object indicates that we are
    updating an existing source and we nuance our check for uniqueness.
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
    filter_extra_fields = True
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


################################################################################
# Secondary Model Validators
################################################################################

class UniqueUnicodeValue(UnicodeString):
    """Validator ensures that the unicode string value is unique in its column.
    The validator must be initialized with modelName and attributeName attributes,
    e.g., UniqueUnicodeValue(modelName='ElicitationMethod', attributeName='name').
    An 'id' attribute on the state object indicates that we are updating and
    should therefore nuance our test for uniqueness.
    """

    messages = {'not_unique':
        'The submitted value for %(modelName)s.%(attributeName)s is not unique.'}

    def validate_python(self, value, state):
        model_ = getattr(model, self.modelName)
        attribute = getattr(model_, self.attributeName)
        id = getattr(state, 'id', None)
        query = Session.query(model_)
        if (id and query.filter(and_(attribute==value, getattr(model_, 'id')!=id)).first()) or \
        (not id and query.filter(attribute==value).first()):
            raise Invalid(self.message('not_unique', state,
                                modelName=self.modelName, attributeName=self.attributeName),
                          value, state)

class ElicitationMethodSchema(Schema):
    """ElicitationMethodSchema is a Schema for validating the data submitted to
    ElicitationmethodsController (controllers/elicitationmethods.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True
    name = UniqueUnicodeValue(max=255, not_empty=True, modelName='ElicitationMethod', attributeName='name')
    description = UnicodeString()

class ValidFormQuery(FancyValidator):
    """Validates a form search query using a SQLAQueryBuilder instance.  Returns
    the query as JSON."""

    messages = {'query_error': u'The submitted query was invalid'}
    def _to_python(self, value, state):
        try:
            queryBuilder = SQLAQueryBuilder('Form', config=state.config)
            query = queryBuilder.getSQLAQuery(value)
        except:
            raise Invalid(self.message('query_error', state), value, state)
        return unicode(json.dumps(value))

class FormSearchSchema(Schema):
    """FormSearchSchema is a Schema for validating the data submitted to
    FormsearchesController (controllers/formsearches.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True
    name = UniqueUnicodeValue(max=255, not_empty=True, modelName='FormSearch', attributeName='name')
    search = ValidFormQuery()
    description = UnicodeString

class OrthographySchema(Schema):
    """OrthographySchema is a Schema for validating the data submitted to
    OrthographyController (controllers/orthography.py).
    """

    allow_extra_fields = True
    filter_extra_fields = True

    name = UnicodeString(max=255, not_empty=True)
    orthography = UnicodeString(not_empty=True)
    lowercase = StringBoolean()
    initialGlottalStops = StringBoolean()

class PageSchema(Schema):
    """PageSchema is a Schema for validating the data submitted to
    PagesController (controllers/pages.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True
    name = UnicodeString(max=255, not_empty=True)
    heading = UnicodeString(max=255)
    markupLanguage = OneOf(h.markupLanguages)
    content = UnicodeString()
    html = UnicodeString()

class SpeakerSchema(Schema):
    """SpeakerSchema is a Schema for validating the data submitted to
    SpeakersController (controllers/speakers.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True
    firstName = UnicodeString(max=255, not_empty=True)
    lastName = UnicodeString(max=255, not_empty=True)
    dialect = UnicodeString(max=255)
    pageContent = UnicodeString()

class SyntacticCategorySchema(Schema):
    """SyntacticCategorySchema is a Schema for validating the data submitted to
    SyntacticcategoriesController (controllers/syntacticcategories.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True
    name = UniqueUnicodeValue(max=255, not_empty=True, modelName='SyntacticCategory', attributeName='name')
    type = OneOf(h.syntacticCategoryTypes)
    description = UnicodeString()

class ValidTagName(FancyValidator):
    """Validator ensures that tag names are unique and prevents the names
    'restricted' and 'foreign word' from being updated.
    """

    messages = {'unchangeable':
        'The names of the restricted and foreign word tags cannot be changed.'}

    def validate_python(self, value, state):
        tag = getattr(state, 'tag', None)
        if tag and tag.name in ('restricted', 'foreign word'):
            raise Invalid(self.message('unchangeable', state), value, state)

class TagSchema(Schema):
    """TagSchema is a Schema for validating the data submitted to
    TagsController (controllers/tags.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True
    chained_validators = [ValidTagName()]
    name = UniqueUnicodeValue(max=255, not_empty=True, modelName='Tag', attributeName='name')
    description = UnicodeString()


################################################################################
# User Validators
################################################################################

class ValidUsernameAndPassword(FancyValidator):
    """Validator for the username, password and password_confirm fields.  Unfortunately,
    I do not know how to throw compound errors so these fields may contain multiple
    errors yet only the first encountered will be returned.
    """

    messages = {
        'bad_password': u' '.join([
            u'The submitted password is invalid; valid passwords contain at least 8 characters',
            u'and either contain at least one character that is not in the printable ASCII range',
            u'or else contain at least one symbol, one digit, one uppercass letter and one lowercase letter.']),
        'no_password': u'A password is required when creating a new user.',
        'not_confirmed': u'The password and password_confirm values do not match.',
        'nonunique_username': u'The username %(username)s is already taken.',
        'illegal_chars': u'The username %(username)s is invalid; only letters of the English alphabet, numbers and the underscore are permitted.',
        'no_username': u'A username is required when creating a new user.',
        'non_admin_username_update': u'Only administrators can update usernames.'
    }

    def _to_python(self, values, state):
        userToUpdate = getattr(state, 'userToUpdate', {})
        userAttemptingUpdate = getattr(state, 'user', {})
        id = userToUpdate.get('id')
        weAreCreating = id is None and True or False
        username = values.get('username', None)
        usernameIsANonEmptyString = type(username) in (str, unicode) and username != u''
        password = values.get('password', None)
        passwordIsANonEmptyString = type(password) in (str, unicode) and password != u''
        password_confirm = values.get('password_confirm', None)

        def containsNonASCIIChars(password):
            return [c for c in password if ord(c) not in range(32, 127)] and True or False

        def isHighEntropyASCII(password):
            """Returns True if the password has a lowercase character, an uppercase
            character, a digit and a symbol.
            """
            symbolPatt = re.compile(u'''[-!$%^&*()_+|~=`{}\[\]:";'<>?,./]''')
            return re.search('[a-z]', password) is not None and \
            re.search('[A-Z]', password) is not None and \
            re.search('[0-9]', password) is not None and \
            symbolPatt.search(password) is not None

        if passwordIsANonEmptyString:
            if len(password) < 8 or (
                not containsNonASCIIChars(password) and not isHighEntropyASCII(password)):
                raise Invalid(self.message('bad_password', state), 'password', state)
            elif password != password_confirm:
                raise Invalid(self.message('not_confirmed', state), 'password', state)
            else:
                values['password'] = password
        else:
            if weAreCreating:
                raise Invalid(self.message('no_password', state), 'password', state)
            else:
                values['password'] = None

        if usernameIsANonEmptyString:
            User = model.User
            query = Session.query(User)
            if re.search('[^\w]+', username):
                # Only word characters are allowed
                raise Invalid(self.message('illegal_chars', state, username=username),
                              'username', state)
            elif (id and query.filter(and_(User.username==username, User.id!=id)).first()) or \
            (not id and query.filter(User.username==username).first()):
                # No duplicate usernames
                raise Invalid(self.message('nonunique_username', state, username=username),
                              'username', state)
            elif userToUpdate and username != userToUpdate['username'] and \
            userAttemptingUpdate['role'] != u'administrator':
                # Non-admins cannot change their usernames
                raise Invalid(self.message('non_admin_username_update', state, username=username),
                              'username', state)
            else:
                values['username'] = username
        else:
            if weAreCreating:
                raise Invalid(self.message('no_username', state), 'username', state)
            else:
                values['username'] = None

        return values

class LicitRoleChange(FancyValidator):
    """Ensures that the role is not being changed by a non-administrator."""

    messages = {'non_admin_role_update': u'Only administrators can update roles.'}

    def validate_python(self, values, state):
        role = values.get('role')
        userToUpdate = getattr(state, 'userToUpdate', {})
        userAttemptingUpdate = getattr(state, 'user', {})
        if userToUpdate and userToUpdate['role'] != role and \
        userAttemptingUpdate['role'] != u'administrator':
            raise Invalid(self.message('non_admin_role_update', state), 'role', state)

class UserSchema(Schema):
    """UserSchema is a Schema for validating the data submitted to
    UsersController (controllers/users.py).
    
    Note: non-admins should not be able to edit their usernames or roles
    """
    allow_extra_fields = True
    filter_extra_fields = True
    chained_validators = [ValidUsernameAndPassword(), LicitRoleChange()]
    username = UnicodeString(max=255)
    password = UnicodeString(max=255)
    password_confirm = UnicodeString(max=255)
    firstName = UnicodeString(max=255, not_empty=True)
    lastName = UnicodeString(max=255, not_empty=True)
    email = Email(max=255, not_empty=True)
    affiliation = UnicodeString(max=255)
    role = OneOf(h.userRoles, not_empty=True)
    markupLanguage = OneOf(h.markupLanguages)
    pageContent = UnicodeString(max=255)
    inputOrthography = ValidOLDModelObject(modelName='Orthography')
    outputOrthography = ValidOLDModelObject(modelName='Orthography')

class PhonologySchema(Schema):
    """PhonologySchema is a Schema for validating the data submitted to
    PhonologiesController (controllers/phonologies.py).
    """
    allow_extra_fields = True
    filter_extra_fields = True
    name = name = UniqueUnicodeValue(max=255, not_empty=True, modelName='Phonology', attributeName='name')
    description = UnicodeString()
    script = UnicodeString()
