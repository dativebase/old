import os
import re
import hashlib
import errno
import datetime
import unicodedata
import string
from uuid import uuid4, UUID
import simplejson as json
from sqlalchemy.sql import or_, not_, desc, asc
import old.model as model
from old.model import Form, FormBackup
from old.model.meta import Session, Model
import orthography
from simplejson.decoder import JSONDecodeError
from paste.deploy import appconfig

################################################################################
# Get data for 'new' action
################################################################################

def getDataForNewAction(GET_params, getterMap, modelNameMap):
    """Return a dictionary whose values are lists of OLD model objects.
    GET_params is the dict-like object created by Pylons that is created on a
    GET request.  The getterMap param is a dict from key names (e.g., 'users')
    to a getter function that retrieves that resource (e.g., getUsers).  The
    modelNameMap is a dict from key names (e.g., 'users') to the relevant model
    (e.g., 'User').

    If no GET parameters are provided (i.e., GET_params is empty), then retrieve
    all data (using getterMap) from the db and return them.

    If GET parameters are specified, then for each parameter whose value is a
    non-empty string (and is not a valid ISO 8601 datetime), retrieve and
    return the appropriate list of objects.

    If the value of a GET parameter is a valid ISO 8601 datetime string,
    retrieve and return the appropriate list of objects *only* if the
    datetime param does *not* match the most recent datetimeModified value
    of the relevant data store (i.e., model object).  This makes sense because a
    non-match indicates that the requester has out-of-date data.
    """

    # result is initialized as a dict with empty list values.
    result = dict([(key, []) for key in getterMap])

    # There are GET params, so we are selective in what we return.
    if GET_params:
        for key in getterMap:
            val = GET_params.get(key)
            # Proceed so long as val is not an empty string.
            if val:
                valAsDatetimeObj = datetimeString2datetime(val)
                if valAsDatetimeObj:
                    # Value of param is an ISO 8601 datetime string that
                    # does not match the most recent datetimeModified of the
                    # relevant model in the db: therefore we return a list
                    # of objects/dicts.  If the datetimes do match, this
                    # indicates that the requester's own stores are
                    # up-to-date so we return nothing.
                    if valAsDatetimeObj != \
                    getMostRecentModificationDatetime(
                        modelNameMap[key]):
                        result[key] = getterMap[key]()
                else:
                    result[key] = getterMap[key]()

    # There are no GET params, so we get everything from the db and return it.
    else:
        for key in getterMap:
            result[key] = getterMap[key]()

    return result


################################################################################
# JSON functionality
################################################################################


def deleteKey(dict_, key_):
    """Try to delete the key_ from the dict_; then return the dict_."""
    try:
        del dict_[key_]
    except:
        pass
    return dict_


class JSONOLDEncoder(json.JSONEncoder):
    """Permits the jsonification of an OLD class instance obj via

        jsonString = json.dumps(obj, cls=JSONOLDEncoder)

    Note: support for additional OLD classes will be implemented as needed ...
    """

    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            elif isinstance(obj, model.User):
                return deleteKey(obj.__dict__, 'password')
            elif isinstance(obj, Model):
                try:
                    return obj.getDict()
                except AttributeError:
                    return obj.__dict__
            else:
                return None


JSONDecodeErrorResponse = json.dumps({'error':
            'JSON decode error: the parameters provided were not valid JSON.'})


################################################################################
# File system functions
################################################################################

def createResearcherDirectory(researcher):
    """Creates a directory named researcher.username in files/researchers/."""
    # I am not entirely sure why pylons.config lacks a 'permanent_store' key
    # when this function is called.  In the getRDBMSName func below I use
    # pylons.config to get 'sqlalchemy.url' ...  WARNING: if test.ini needs a
    # distinct researcher directory (it shouldn't), then the 'config:test.ini'
    # should be passed to appconfig here.
    config = appconfig('config:development.ini', relative_to='.')
    directoryPath = os.path.join(
        config['permanent_store'], 'researchers',
        researcher.username
    )
    makeDirectorySafely(directoryPath)


def makeDirectorySafely(path):
    """Create a directory and avoid race conditions.  Taken from 
    http://stackoverflow.com/questions/273192/python-best-way-to-create-directory-if-it-doesnt-exist-for-file-write.
    Listed as make_sure_path_exists.
    """

    try:
        os.makedirs(path)
    except OSError, exception:
        if exception.errno != errno.EEXIST:
            raise


################################################################################
# String functions
################################################################################

def toSingleSpace(string):
    """Remove leading and trailing whitespace and replace newlines, tabs and
    sequences of 2 or more space to one space.
    """

    patt = re.compile(' {2,}')
    return patt.sub(' ', string.strip().replace('\n', ' ').replace('\t', ' '))


def removeAllWhiteSpace(string):
    """Remove all spaces, newlines and tabs."""
    return string.replace('\n', '').replace('\t', '').replace(' ', '')


def escREMetaChars(string):
    """Escapes regex metacharacters so that we can formulate an SQL regular
    expression based on an arbitrary, user-specified inventory of
    graphemes/polygraphs.

        >>> escREMetaChars(u'-')
        u'\\\-'

    """

    def esc(c):
        if c in u'\\^$*+?{,}.|][()^-':
            return re.escape(c)
        return c
    return ''.join([esc(c) for c in string])


def camelCase2lowerSpace(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1).lower()


################################################################################
# Unicode functions
################################################################################


def normalize(unistr):
    """Return a unistr using canonical decompositional normalization (NFD)."""

    try:
        return unicodedata.normalize('NFD', unistr)
    except TypeError:
        return unicodedata.normalize('NFD', unicode(unistr))
    except UnicodeDecodeError:
        return unistr


def getUnicodeNames(string):
    """Returns a string of comma-delimited unicode character names corresponding
    to the characters in the input string.

    """

    try:
        return ', '.join([unicodedata.name(c, u'<no name>') for c in string])
    except TypeError:
        return ', '.join([unicodedata.name(unicode(c), u'<no name>')
                          for c in string])
    except UnicodeDecodeError:
        return string


def getUnicodeCodePoints(string):
    """Returns a string of comma-delimited unicode code points corresponding
    to the characters in the input string.

    """

    return ', '.join(['U+%04X' % ord(c) for c in string])



def normalizeDict(dict_):
    """NFD normalize all unicode values in dict_.
    
    """

    for k in dict_:
        try:
            dict_[k] = normalize(dict_[k])
        except TypeError:
            pass
    return dict_


################################################################################
# ApplicationSettings
################################################################################

class ApplicationSettings(object):
    """ApplicationSettings is a class that adds functionality to a
    ApplicationSettings object.

    The value of the applicationSettings attribute is the most recently added
    ApplicationSettings model.  Other values, e.g., storageOrthography or
    morphemeBreakInventory, are class instances or other data structures built
    upon the application settings properties.
    """

    def __init__(self):
        self.applicationSettings = getApplicationSettings()
        if self.applicationSettings:
            self.getAttributes()

    def getAttributes(self):
        """Generate some higher-level data structures for the application
        settings model, providing sensible defaults where appropriate.
        """
        self.morphemeDelimiters = []
        if self.applicationSettings.morphemeDelimiters:
            self.morphemeDelimiters = \
                        self.applicationSettings.morphemeDelimiters.split(u',')

        self.punctuation = []
        if self.applicationSettings.punctuation:
            self.punctuation = list(self.applicationSettings.punctuation)

        self.grammaticalities = [u'']
        if self.applicationSettings.grammaticalities:
            self.grammaticalities = [u''] + \
                        self.applicationSettings.grammaticalities.split(u',')

        foreignWordNarrowPhoneticTranscriptions, \
        foreignWordBroadPhoneticTranscriptions, \
        foreignWordOrthographicTranscriptions, \
        foreignWordMorphemicTranscriptions = getForeignWordTranscriptions()

        self.storageOrthography = []
        if self.applicationSettings.storageOrthography and \
        self.applicationSettings.storageOrthography.orthography:
            self.storageOrthography = \
                self.applicationSettings.storageOrthography.orthography.split(',')

        self.punctuationInventory = Inventory(self.punctuation)
        self.morphemeDelimitersInventory = Inventory(self.morphemeDelimiters)
        self.narrowPhoneticInventory = Inventory(
            foreignWordNarrowPhoneticTranscriptions + [u' '] + 
            self.applicationSettings.narrowPhoneticInventory.split(','))
        self.broadPhoneticInventory = Inventory(
            foreignWordBroadPhoneticTranscriptions + [u' '] + 
            self.applicationSettings.broadPhoneticInventory.split(','))
        self.orthographicInventory = Inventory(
            foreignWordOrthographicTranscriptions + 
            self.punctuation + [u' '] + self.storageOrthography)
        if self.applicationSettings.morphemeBreakIsOrthographic:
            self.morphemeBreakInventory = Inventory(
                foreignWordMorphemicTranscriptions +
                self.morphemeDelimiters + [u' '] + self.storageOrthography)
        else:
            self.morphemeBreakInventory = Inventory(
                foreignWordMorphemicTranscriptions + 
                self.morphemeDelimiters + [u' '] +
                self.applicationSettings.phonemicInventory.split(','))


################################################################################
# Inventory
################################################################################

class Inventory:
    """An inventory is a set of graphemes/polygraphs/characters.  Initialization
    requires a list.

    This class should be the base class from which the Orthography class
    inherits but I don't have time to implement that right now.
    """

    def __init__(self, inputList):
        self.inputList = inputList
        self._getUnicodeMetadata(inputList)
        self._setRegexValidator(inputList)
        self._compileRegexValidator(self.regexValidator)

    def _getUnicodeMetadata(self, inputList):
        self.inventoryWithUnicodeMetadata = [self._getNamesAndCodePoints(g)
                                             for g in inputList]

    def _getNamesAndCodePoints(self, graph):
        return (graph, getUnicodeNames(graph), getUnicodeCodePoints(graph))

    def _setRegexValidator(self, inputList):
        disjPatt = u'|'.join([escREMetaChars(g) for g in inputList])
        self.regexValidator = u'^(%s)*$' % disjPatt

    def _compileRegexValidator(self, regexValidator):
        self.compiledRegexValidator = re.compile(regexValidator)

    def getInputList(self):
        return self.inputList

    def getRegexValidator(self, substr=False):
        """Returns a regex that matches only strings composed of zero or more
        of the graphemes in the inventory (plus the space character).
        """

        return self.regexValidator

    def getNonMatchingSubstrings(self, string):
        """Return a list of substrings of string that are not constructable
        using the inventory.  This is useful for showing invalid substrings.
        """

        regex = u'|'.join([escREMetaChars(g) for g in self.inputList])
        regex = u'(%s)+' % regex
        patt = re.compile(regex)
        list_ = patt.split(string)
        nonMatchingSubstrings = [escREMetaChars(x) for x in list_[::2] if x]
        return nonMatchingSubstrings

    def stringIsValid(self, string):
        """Return False if string cannot be generated by concatenating the
        elements of the orthography; otherwise, return True.
        """

        if self.compiledRegexValidator.match(string):
            return True
        return False



################################################################################
# EventHook -- NOT BEING USED (YET?)
################################################################################

class EventHook(object):
    """EventHook is for event-based (PubSub) stuff in Python.  It is taken from
    http://www.voidspace.org.uk/python/weblog/arch_d7_2007_02_03.shtml#e616.
    See also http://stackoverflow.com/questions/1092531/event-system-in-python.
    """

    def __init__(self):
        self.__handlers = []

    def __iadd__(self, handler):
        """eh = EventHook(); eh += handler."""
        self.__handlers.append(handler)
        return self

    def __isub__(self, handler):
        """... eh -= handler."""
        self.__handlers.remove(handler)
        return self

    def fire(self, *args, **keywargs):
        for handler in self.__handlers:
            handler(*args, **keywargs)

    def clearObjectHandlers(self, inObject):
        for theHandler in self.__handlers:
            if theHandler.im_self == inObject:
                self -= theHandler




################################################################################
# Foreign word functions
################################################################################


def getForeignWords():
    """Return the forms that are tagged with a 'foreign word' tag.  This is
    useful for input validation as foreign words may contain otherwise illicit
    characters/graphemes.
    """

    foreignWordTag = getForeignWordTag()
    if foreignWordTag:
        return Session.query(Form).filter(
            Form.tags.contains(foreignWordTag)).all()
    else:
        return getForms()


def getForeignWordTranscriptions():
    """Returns a 4-tuple (fWNarrPhonTranscrs, fWBroadPhonTranscrs,
    fWOrthTranscrs, fWMorphTranscrs) where each element is a list of
    transcriptions (narrow phonetic, broad phonetic, orthographic, morphemic)
    of foreign words.

    """

    foreignWords = getForeignWords()
    fWNarrPhonTranscrs = []
    fWBroadPhonTranscrs = []
    fWOrthTranscrs = []
    fWMorphTranscrs = []
    for fw in foreignWords:
        if fw.narrowPhoneticTranscription:
            fWNarrPhonTranscrs.append(fw.narrowPhoneticTranscription)
        if fw.phoneticTranscription:
            fWBroadPhonTranscrs.append(fw.phoneticTranscription)
        if fw.morphemeBreak:
            fWMorphTranscrs.append(fw.morphemeBreak)
        fWOrthTranscrs.append(fw.transcription)
    return (fWNarrPhonTranscrs, fWBroadPhonTranscrs, fWOrthTranscrs, fWMorphTranscrs)



def formIsForeignWord(form):
    foreignWordTag = getForeignWordTag()
    if foreignWordTag in form.tags:
        return True
    return False


def getForeignWordTagId():
    return getForeignWordTag().id


################################################################################
# Query Convenience Functions
################################################################################

def getGrammaticalities():
    try:
        return getApplicationSettings().grammaticalities.replace(
                                                            ' ', '').split(',')
    except AttributeError:
        return []

def getMorphemeDelimiters():
    applicationSettings = getApplicationSettings()
    try:
        morphemeDelimiters = applicationSettings.morphemeDelimiters
    except AttributeError:
        return []
    try:
        return morphemeDelimiters.split(',')
    except AttributeError:
        return []

def getApplicationSettings():
    return Session.query(model.ApplicationSettings).order_by(
        desc(model.ApplicationSettings.id)).first()

def getOrthographies():

    return getModelsByName('Orthography')

def getLanguages():
    return getModelsByName('Language')

def getElicitationMethods():
    return getModelsByName('ElicitationMethod')

def getFormsUserCanAccess(user, paginator=None):
    entererCondition = Form.enterer == user
    restrictedTag = getRestrictedTag()
    unrestrictedCondition = not_(Form.tags.contains(restrictedTag))
    filteredQuery = Session.query(Form).filter(
        or_(entererCondition, unrestrictedCondition)).order_by(asc(Form.id))
    if paginator:
        return filteredQuery.slice(paginator['start'], paginator['end']).all()
    return filteredQuery.all()

def getForms(paginator=None):
    formQuery = Session.query(Form).order_by(asc(Form.id))
    if paginator:
        return formQuery.slice(paginator['start'], paginator['end']).all()
    return formQuery.all()

def getFormByUUID(UUID):
    """Return the Form models with UUID."""
    return Session.query(Form).filter(Form.UUID==UUID).first()

def getFormBackupsByUUID(UUID):
    """Return all FormBackup models with UUID = UUID."""
    return Session.query(FormBackup).filter(
        FormBackup.UUID==UUID).order_by(desc(
        FormBackup.id)).all()

def getFormBackupsByFormId(formId):
    """Return all FormBackup models with form_id = formId.  WARNING: unexpected
    data may be returned (on an SQLite backend) if primary key ids of deleted
    forms are recycled.
    """
    return Session.query(FormBackup).filter(
        FormBackup.form_id==formId).order_by(desc(
        FormBackup.id)).all()

def getTags():
    return getModelsByName('Tag')

def getFiles():
    return getModelsByName('File')

def getForeignWordTag():
    return Session.query(model.Tag).filter(
        model.Tag.name == u'foreign word').first()

def getRestrictedTag():
    return Session.query(model.Tag).filter(
        model.Tag.name == u'restricted').first()

def getSyntacticCategories():
    return getModelsByName('SyntacticCategory')

def getSpeakers():
    return getModelsByName('Speaker')

def getUsers():
    return getModelsByName('User')

def getSources():
    return getModelsByName('Source')

def getModelNames():
    return [mn for mn in dir(model) if mn[0].isupper()
            and mn not in ('Model', 'Base', 'Session')]

def getModelsByName(modelName):
    return getQueryByModelName(modelName).all()

def getQueryByModelName(modelName):
    return Session.query(getattr(model, modelName))

def clearAllModels(retain=['Language']):
    """Convenience function for removing all OLD models from the database.
    The retain parameter is a list of model names that should not be cleared.
    """
    for modelName in getModelNames():
        if modelName not in retain:
            models = getModelsByName(modelName)
            for model in models:
                Session.delete(model)
    Session.commit()

def getAllModels():
    return dict([(mn, getModelsByName(mn)) for mn in getModelNames()])

################################################################################
# OLD model objects getters: for defaults and testing
################################################################################

def generateDefaultAdministrator():
    admin = model.User()
    admin.firstName = u'Admin'
    admin.lastName = u'Admin'
    admin.username = u'admin'
    admin.email = u'admin@example.com'
    admin.password = unicode(hashlib.sha224(u'admin').hexdigest())
    admin.role = u'administrator'
    admin.collectionViewType = u'long'
    admin.inputOrthography = None
    admin.outputOrthography = None
    admin.personalPageContent = u''
    createResearcherDirectory(admin)
    return admin

def generateDefaultContributor():
    contributor = model.User()
    contributor.firstName = u'Contributor'
    contributor.lastName = u'Contributor'
    contributor.username = u'contributor'
    contributor.email = u'contributor@example.com'
    contributor.password = unicode(hashlib.sha224(u'contributor').hexdigest())
    contributor.role = u'contributor'
    contributor.collectionViewType = u'long'
    contributor.inputOrthography = None
    contributor.outputOrthography = None
    contributor.personalPageContent = u''
    createResearcherDirectory(contributor)
    return contributor

def generateDefaultViewer():
    viewer = model.User()
    viewer.firstName = u'Viewer'
    viewer.lastName = u'Viewer'
    viewer.username = u'viewer'
    viewer.email = u'viewer@example.com'
    viewer.password = unicode(hashlib.sha224(u'viewer').hexdigest())
    viewer.role = u'viewer'
    viewer.collectionViewType = u'long'
    viewer.inputOrthography = None
    viewer.outputOrthography = None
    viewer.personalPageContent = u''
    createResearcherDirectory(viewer)
    return viewer

def generateDefaultHomePage():
    homepage = model.Page()
    homepage.name = u'home'
    homepage.heading = u'Welcome to the OLD'
    homepage.markup = u'reStructuredText'
    homepage.content = u"""
The Online Linguistic Database is a web application that helps people to
document, study and learn a language.
        """
    homepage.markup = u'restructuredtext'
    return homepage

def generateDefaultHelpPage():
    helppage = model.Page()
    helppage.name = u'help'
    helppage.heading = u'OLD Application Help'
    helppage.markup = u'reStructuredText'
    helppage.content = u"""
Welcome to the help page of this OLD application.

This page should contain content entered by your administrator.
        """
    helppage.markup = u'restructuredtext'
    return helppage

def generateDefaultOrthography1():
    orthography1 = model.Orthography()
    orthography1.name = u'Sample Orthography 1'
    orthography1.orthography = u'p,t,k,m,s,[i,i_],[a,a_],[o,o_]'
    orthography1.lowercase = True
    orthography1.initialGlottalStops = True
    return orthography1

def generateDefaultOrthography2():
    orthography2 = model.Orthography()
    orthography2.name = u'Sample Orthography 2'
    orthography2.orthography = u'b,d,g,m,s,[i,i\u0301],[a,a\u0301],[o,o\u0301]'
    orthography2.lowercase = True
    orthography2.initialGlottalStops = True
    return orthography2

def generateDefaultApplicationSettings(orthographies=[], unrestrictedUsers=[]):
    englishOrthography = u', '.join(list(string.ascii_lowercase))
    applicationSettings = model.ApplicationSettings()
    applicationSettings.objectLanguageName = u'Unspecified'
    applicationSettings.objectLanguageId = u'uns'
    applicationSettings.metalanguageName = u'English'
    applicationSettings.metalanguageId = u'eng'
    applicationSettings.metalanguageInventory = englishOrthography
    applicationSettings.orthographicValidation = u'None'
    applicationSettings.narrowPhoneticInventory = u''
    applicationSettings.narrowPhoneticValidation = u'None'
    applicationSettings.broadPhoneticInventory = u''
    applicationSettings.broadPhoneticValidation = u'None'
    applicationSettings.narrowPhoneticInventory = u''
    applicationSettings.narrowPhoneticValidation = u'None'
    applicationSettings.morphemeBreakIsOrthographic = False
    applicationSettings.morphemeBreakValidation = u'None'
    applicationSettings.phonemicInventory = u''
    applicationSettings.morphemeDelimiters = u'-,='
    applicationSettings.punctuation = u""".,;:!?'"\u2018\u2019\u201C\u201D[]{}()-"""
    applicationSettings.grammaticalities = u'*,#,?'
    applicationSettings.storageOrthography = orthographies[1] if 1 < len(orthographies) else None
    applicationSettings.inputOrthography = orthographies[0] if 0 < len(orthographies) else None
    applicationSettings.outputOrthography = orthographies[0] if 0 < len(orthographies) else None
    applicationSettings.unrestrictedUsers = unrestrictedUsers
    applicationSettings.orthographies = orthographies
    return applicationSettings

def generateRestrictedTag():
    restrictedTag = model.Tag()
    restrictedTag.name = u'restricted'
    restrictedTag.description = u'''Forms tagged with the tag 'restricted'
can only be viewed by administrators, unrestricted users and the users they were
entered by.'''
    return restrictedTag

def generateForeignWordTag():
    foreignWordTag = model.Tag()
    foreignWordTag.name = u'foreign word'
    foreignWordTag.description = u'''Use this tag for lexical entries that are
not from the object language. For example, it might be desirable to create a
form as lexical entry for a proper noun like "John".  Such a form should be
tagged as a "foreign word". This will allow forms containing "John" to have
gapless syntactic category string values. Additionally, the system ignores
foreign word transcriptions when validating user input against orthographic,
phonetic and phonemic inventories.'''
    return foreignWordTag

def generateDefaultForm():
    form = Form()
    form.UUID = unicode(uuid4())
    form.transcription = u'test transcription'
    form.morphemeBreakIDs = u'null'
    form.morphemeGlossIDs = u'null'
    form.datetimeEntered = now()
    gloss = model.Gloss()
    gloss.gloss = u'test gloss'
    form.glosses.append(gloss)
    return form

def generateDefaultFile():
    file = model.File()
    file.name = u'test_file_name' # VARCHAR 255, UNIQUE
    file.MIMEtype = u'image/jpeg' # VARCHAR 255
    file.size = 1024 # INT
    file.description = u'An image of the land.' # TEXT
    #dateElicited # DATE
    #elicitor # INT, FOREIGN KEY: USER ID
    #enterer # INT, FOREIGN KEY: USER ID
    #speaker # INT, FOREIGN KEY: SPEAKER ID
    #utteranceType # VARCHAR 255
    #embeddedFileMarkup # TEXT
    #embeddedFilePassword # VARCHAR 255
    return file

def generateDefaultElicitationMethod():
    elicitationMethod = model.ElicitationMethod()
    elicitationMethod.name = u'test elicitation method'
    elicitationMethod.description = u'test elicitation method description'
    return elicitationMethod

def generateSSyntacticCategory():
    syntacticCategory = model.SyntacticCategory()
    syntacticCategory.name = u'S'
    syntacticCategory.description = u'Tag sentences with S.'
    return syntacticCategory

def generateNSyntacticCategory():
    syntacticCategory = model.SyntacticCategory()
    syntacticCategory.name = u'N'
    syntacticCategory.description = u'Tag nouns with N.'
    return syntacticCategory

def generateVSyntacticCategory():
    syntacticCategory = model.SyntacticCategory()
    syntacticCategory.name = u'V'
    syntacticCategory.description = u'Tag verbs with V.'
    return syntacticCategory

def generateNumSyntacticCategory():
    syntacticCategory = model.SyntacticCategory()
    syntacticCategory.name = u'Num'
    syntacticCategory.description = u'Tag number morphology with Num.'
    return syntacticCategory

def generateDefaultSpeaker():
    speaker = model.Speaker()
    speaker.firstName = u'test speaker first name'
    speaker.lastName = u'test speaker last name'
    speaker.dialect = u'test speaker dialect'
    speaker.speakerPageContent = u'test speaker page content'
    return speaker

def generateDefaultUser():
    user = model.User()
    user.username = u'test user username'
    user.firstName = u'test user first name'
    user.lastName = u'test user last name'
    user.email = u'test user email'
    user.affiliation = u'test user affiliation'
    user.role = u'contributor'
    user.personalPageContent = u'test user page content'
    return user

def generateDefaultSource():
    source = model.Source()
    source.authorFirstName = u'test source author first name'
    source.authorLastName = u'test source author last name'
    source.title = u'test source title'
    source.year = 1999
    source.fullReference = u'test source full reference'
    return source

################################################################################
# Date & Time-related Functions
################################################################################


def now():
    return datetime.datetime.utcnow()


def getMostRecentModificationDatetime(modelName):
    """Return the most recent datetimeModified attribute for the model with the
    provided modelName.  If the modelName is not recognized, return None.
    """

    OLDModel = getattr(model, modelName, None)
    if OLDModel:
        return Session.query(OLDModel).order_by(
            desc(OLDModel.datetimeModified)).first().datetimeModified
    return OLDModel


def datetimeString2datetime(datetimeString):
    """Parse an ISO 8601-formatted datetime into a Python datetime object.
    Cf. http://stackoverflow.com/questions/531157/parsing-datetime-strings-with-microseconds

    Previously called ISO8601Str2datetime.
    """

    try:
        parts = datetimeString.split('.')
        yearsToSecondsString = parts[0]
        datetimeObject = datetime.datetime.strptime(yearsToSecondsString,
                                                    "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    try:
        microseconds = int(parts[1])
        return datetimeObject.replace(microsecond=microseconds)
    except (IndexError, ValueError, OverflowError):
        return datetimeObject


def dateString2date(dateString):
    """Parse an ISO 8601-formatted date into a Python date object."""
    try:
        return datetime.datetime.strptime(dateString, "%Y-%m-%d").date()
    except ValueError:
        return None


################################################################################
# Miscellaneous Functions & Classes
################################################################################

def getInt(int_):
    try:
        return int(int_)
    except (ValueError, TypeError):
        return None

class FakeForm(object):
    pass

################################################################################
# Authorization Functions
################################################################################

def userIsAuthorizedToAccessForm(user, form, unrestrictedUsers):
    """Return True if the user is authorized to access the form.  Forms tagged
    with the 'restricted' tag are only accessible to administrators, their
    enterers and unrestricted users.
    """

    if isinstance(form, Form):
        formTags = form.tags
        formTagNames = [t.name for t in form.tags]
        entererId = form.enterer_id
    else:
        formBackupDict = form.getDict()
        formTags = formBackupDict['tags']
        formTagNames = [t['name'] for t in formTags]
        entererId = formBackupDict['enterer'].get('id', None)
    return not formTags or \
        'restricted' not in formTagNames or \
        user in unrestrictedUsers or \
        user.id == entererId or \
        user.role == u'administrator'


def userIsUnrestricted(user, unrestrictedUsers):
    """Return True if the user is an administrator, unrestricted or there is no
    restricted tag.
    """
    restrictedTag = getRestrictedTag()
    return not restrictedTag or user.role == u'administrator' or \
                                           user in unrestrictedUsers


unauthorizedJSONMsg = json.dumps(
    {'error': 'You are not authorized to access this resource.'})



def getRDBMSName():
    #config = appconfig('config:development.ini', relative_to='.')
    from pylons import config as config_
    SQLAlchemyURL = config_['sqlalchemy.url']
    return SQLAlchemyURL.split(':')[0]
