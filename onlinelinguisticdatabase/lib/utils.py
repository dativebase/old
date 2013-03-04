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

"""
The utils module is really cool!
------------------------------------

A Sphinx/reST Python code block example:

.. code-block:: python

    class NewPageForm(formencode.Schema):
        allow_extra_fields = True
        filter_extra_fields = True
        content = formencode.validators.String(
            not_empty=True,
            messages={
                'empty':'Please enter some content for the page. '
            }
        )
        heading = formencode.validators.String()
        title = formencode.validators.String(not_empty=True)

"""

import os
import re
import errno
import datetime
import unicodedata
import string
import smtplib
import ConfigParser
from random import choice, shuffle
from shutil import rmtree
from passlib.hash import pbkdf2_sha512
from uuid import uuid4, UUID
from mimetypes import guess_type
import simplejson as json
from sqlalchemy.sql import or_, not_, desc, asc
from sqlalchemy.orm import subqueryload, joinedload
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model import Form, FormBackup, File, Collection, CollectionBackup
from onlinelinguisticdatabase.model.meta import Session, Model
import orthography
from simplejson.decoder import JSONDecodeError
from paste.deploy import appconfig
from paste.deploy.converters import asbool
from pylons import app_globals, session, url
from formencode.schema import Schema
from formencode.validators import Int, UnicodeString, OneOf
from markdown import Markdown
from docutils.core import publish_parts
from decorator import decorator
from pylons.decorators.util import get_pylons
from subprocess import Popen, PIPE

import logging

log = logging.getLogger(__name__)

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
            elif isinstance(obj, Model):
                try:
                    return obj.getDict()
                except AttributeError:
                    return obj.__dict__
            else:
                return None


JSONDecodeErrorResponse = {'error': 'JSON decode error: the parameters provided were not valid JSON.'}


@decorator
def jsonify(func, *args, **kwargs):
    """Action decorator that formats output for JSON

    Given a function that will return content, this decorator will turn
    the result into JSON, with a content-type of 'application/json' and
    output it.

    Adapted from pylons.decorators.

    """
    pylons = get_pylons(args)
    pylons.response.headers['Content-Type'] = 'application/json'
    data = func(*args, **kwargs)
    return json.dumps(data, cls=JSONOLDEncoder)


def restrict(*methods):
    """Restricts access to the function depending on HTTP method

    Just like pylons.decorators.rest.restrict except it returns JSON.
    """
    def check_methods(func, *args, **kwargs):
        """Wrapper for restrict"""
        pylons = get_pylons(args)
        if pylons.request.method not in methods:
            pylons.response.headers['Content-Type'] = 'application/json'
            pylons.response.status_int = 405
            return {'error':
                'The %s method is not permitted for this resource; permitted method(s): %s' % (
                    pylons.request.method, ', '.join(methods))}
        return func(*args, **kwargs)
    return decorator(check_methods)

################################################################################
# File system functions
################################################################################

def getConfig(**kwargs):
    """Try desperately to get a Pylons config object.  The best thing is if a
    config object is passed in kwargs['config'].
    """
    config = kwargs.get('config')
    configFilename = kwargs.get('configFilename')
    if config:
        return config
    elif configFilename:
        return appconfig('config:%s' % configFilename, relative_to='.')
    else:
        try:
            return appconfig('config:production.ini', relative_to='.')
        except:
            try:
                return appconfig('config:development.ini', relative_to='.')
            except:
                try:
                    return appconfig('config:test.ini', relative_to='.')
                except:
                    from pylons import config
                    return config

def createResearcherDirectory(researcher, **kwargs):
    """Creates a directory named researcher.username in files/researchers/."""
    config = getConfig(**kwargs)
    try:
        permanent_store = config['permanent_store']
        directoryPath = os.path.join(permanent_store, 'researchers', researcher.username)
        makeDirectorySafely(directoryPath)
    except (TypeError, KeyError):
        raise Exception('The config object was inadequate.')

def destroyResearcherDirectory(researcher, **kwargs):
    """Destroys a directory named researcher.username in files/researchers/."""
    config = getConfig(**kwargs)
    try:
        permanent_store = config['permanent_store']
        directoryPath = os.path.join(permanent_store, 'researchers', researcher.username)
        rmtree(directoryPath)
    except (TypeError, KeyError):
        raise Exception('The config object was inadequate.')

def destroyAllResearcherDirectories(**kwargs):
    """Removes all directories from files/researchers/."""
    config = getConfig(**kwargs)
    try:
        researchersPath = os.path.join(config['permanent_store'], 'researchers')
        for name in os.listdir(researchersPath):
            path = os.path.join(researchersPath, name)
            if os.path.isdir(path):
                rmtree(path)
    except (TypeError, KeyError):
        raise Exception('The config object was inadequate.')

def renameResearcherDirectory(oldName, newName, **kwargs):
    config = getConfig(**kwargs)
    try:
        oldPath = os.path.join(config['permanent_store'], 'researchers', oldName)
        newPath = os.path.join(config['permanent_store'], 'researchers', newName)
        try:
            os.rename(oldPath, newPath)
        except OSError:
            makeDirectorySafely(newPath)
    except (TypeError, KeyError):
        raise Exception('The config object was inadequate.')

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

def secureFilename(path):
    """Removes null bytes, path.sep and path.altsep from a path.
    From http://lucumr.pocoo.org/2010/12/24/common-mistakes-as-web-developer/
    """
    patt = re.compile(r'[\0%s]' % re.escape(''.join(
        [os.path.sep, os.path.altsep or ''])))
    return patt.sub('', path)

def cleanAndSecureFilename(path):
    return secureFilename(path).replace("'", "").replace('"', '').replace(' ', '_')


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
    """Return the morpheme delimiters from app settings as a list."""
    applicationSettings = getApplicationSettings()
    try:
        morphemeDelimiters = applicationSettings.morphemeDelimiters
    except AttributeError:
        return []
    try:
        return morphemeDelimiters and morphemeDelimiters.split(',') or []
    except AttributeError:
        return []

def isLexical(form):
    """Return True if the input form is lexical, i.e, if neither its morpheme
    break nor its morpheme gloss lines contain the space character or any of the
    morpheme delimiters.  Note: designed to work on dict representations of forms
    also.
    """
    delimiters = getMorphemeDelimiters() + [' ']
    try:
        return bool(form.morphemeBreak) and bool(form.morphemeGloss) and not (
                    set(delimiters) & set(form.morphemeBreak) and
                    set(delimiters) & set(form.morphemeGloss))
    except AttributeError:
        return bool(form['morphemeBreak']) and bool(form['morphemeGloss']) and not (
                    set(delimiters) & set(form['morphemeBreak']) and
                    set(delimiters) & set(form['morphemeGloss']))
    except:
        return False

def getApplicationSettings():
    return Session.query(model.ApplicationSettings).order_by(
        desc(model.ApplicationSettings.id)).first()

def getOrthographies(sortByIdAsc=False):
    return getModelsByName('Orthography', sortByIdAsc)

def getFormSearches(sortByIdAsc=False):
    return getModelsByName('FormSearch', sortByIdAsc)

def getPages(sortByIdAsc=False):
    return getModelsByName('Page', sortByIdAsc)

def getPhonologies(sortByIdAsc=False):
    return getModelsByName('Phonology', sortByIdAsc)

def getLanguages(sortByIdAsc=False):
    return getModelsByName('Language', sortByIdAsc)

def getElicitationMethods(sortByIdAsc=False):
    return getModelsByName('ElicitationMethod', sortByIdAsc)

def getStartAndEndFromPaginator(paginator):
    start = (paginator['page'] - 1) * paginator['itemsPerPage']
    return (start, start + paginator['itemsPerPage'])

def filterRestrictedModels(modelName, query, user=None):
    user = user or session['user']
    unrestrictedUsers = getUnrestrictedUsers()
    userIsUnrestricted_ = userIsUnrestricted(user, unrestrictedUsers)
    if userIsUnrestricted_:
        return query
    else:
        return filterRestrictedModelsFromQuery(modelName, query, user)

def filterRestrictedModelsFromQuery(modelName, query, user):
    model_ = getattr(model, modelName)
    if modelName in (u'FormBackup', u'CollectionBackup'):
        entererCondition = model_.enterer.like(u'%' + u'"id": %d' % user.id + u'%')
        unrestrictedCondition = not_(model_.tags.like(u'%"name": "restricted"%'))
    else:
        entererCondition = model_.enterer == user
        restrictedTag = getRestrictedTag()
        unrestrictedCondition = not_(model_.tags.contains(restrictedTag))
    return query.filter(or_(entererCondition, unrestrictedCondition))

def getFormsUserCanAccess(user, paginator=None):
    query = filterRestrictedModelsFromQuery(Session.query(Form), user).order_by(
        asc(Form.id))
    if paginator:
        start, end = getStartAndEndFromPaginator(paginator)
        return query.slice(start, end).all()
    return query.all()

def getForms(paginator=None, eagerload=False):
    formQuery = Session.query(Form).order_by(asc(Form.id))
    if eagerload:
        formQuery = eagerloadForm(formQuery)
    if paginator:
        start, end = getStartAndEndFromPaginator(paginator)
        return formQuery.slice(start, end).all()
    return formQuery.all()

def getFormByUUID(UUID):
    """Return the first (and only, hopefully) Form model with UUID."""
    return eagerloadForm(Session.query(Form)).filter(Form.UUID==UUID).first()

def getCollectionByUUID(UUID):
    """Return the first (and only, hopefully) Collection model with UUID."""
    return Session.query(Collection).filter(Collection.UUID==UUID).first()

def getFormBackupsByUUID(UUID):
    """Return all FormBackup models with UUID = UUID."""
    return Session.query(FormBackup).filter(
        FormBackup.UUID==UUID).order_by(desc(
        FormBackup.id)).all()

def getCollectionBackupsByUUID(UUID):
    """Return all CollectionBackup models with UUID = UUID."""
    return Session.query(CollectionBackup).filter(
        CollectionBackup.UUID==UUID).order_by(desc(
        CollectionBackup.id)).all()

def getFormBackupsByFormId(formId):
    """Return all FormBackup models with form_id = formId.  WARNING: unexpected
    data may be returned (on an SQLite backend) if primary key ids of deleted
    forms are recycled.
    """
    return Session.query(FormBackup).filter(
        FormBackup.form_id==formId).order_by(desc(
        FormBackup.id)).all()

def getCollectionBackupsByCollectionId(collectionId):
    """Return all CollectionBackup models with collection_id = collectionId.
    WARNING: unexpected data may be returned (on an SQLite backend) if primary
    key ids of deleted collections are recycled.
    """
    return Session.query(CollectionBackup).filter(
        CollectionBackup.collection_id==collectionId).order_by(desc(
        CollectionBackup.id)).all()

def getCollections():
    return getModelsByName('Collection', True)

def getTags(sortByIdAsc=False):
    return getModelsByName('Tag', sortByIdAsc)

def getFiles():
    return getModelsByName('File', True)

def getForeignWordTag():
    return Session.query(model.Tag).filter(
        model.Tag.name == u'foreign word').first()

def getRestrictedTag():
    return Session.query(model.Tag).filter(
        model.Tag.name == u'restricted').first()

def getSyntacticCategories(sortByIdAsc=False):
    return getModelsByName('SyntacticCategory', sortByIdAsc)

def getSpeakers(sortByIdAsc=False):
    return getModelsByName('Speaker', sortByIdAsc)

def getUsers(sortByIdAsc=False):
    return getModelsByName('User', sortByIdAsc)

def getMiniDictsGetter(modelName, sortByIdAsc=False):
    def func():
        models = getModelsByName(modelName, sortByIdAsc)
        return [m.getMiniDict() for m in models]
    return func

def getSources(sortByIdAsc=False):
    return getModelsByName('Source', sortByIdAsc)

def getModelNames():
    return [mn for mn in dir(model) if mn[0].isupper()
            and mn not in ('Model', 'Base', 'Session')]

def getModelsByName(modelName, sortByIdAsc=False):
    return getQueryByModelName(modelName, sortByIdAsc).all()

def getQueryByModelName(modelName, sortByIdAsc=False):
    model_ = getattr(model, modelName)
    if sortByIdAsc:
        return Session.query(model_).order_by(asc(getattr(model_, 'id')))
    return Session.query(model_)

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

def getPaginatedQueryResults(query, paginator):
    if 'count' not in paginator:
        paginator['count'] = query.count()
    start, end = getStartAndEndFromPaginator(paginator)
    return {
        'paginator': paginator,
        'items': query.slice(start, end).all()
    }

def addPagination(query, paginator):
    if paginator and paginator.get('page') is not None and \
    paginator.get('itemsPerPage') is not None:
        paginator = PaginatorSchema.to_python(paginator)    # raises formencode.Invalid if paginator is invalid
        return getPaginatedQueryResults(query, paginator)
    else:
        return query.all()

def addOrderBy(query, orderByParams, queryBuilder, primaryKey='id'):
    """Add an ORDER BY clause to the query using the getSQLAOrderBy method of
    the supplied queryBuilder (if possible) or using a default ORDER BY <primaryKey> ASC.
    """
    if orderByParams and orderByParams.get('orderByModel') and \
    orderByParams.get('orderByAttribute') and orderByParams.get('orderByDirection'):
        orderByParams = OrderBySchema.to_python(orderByParams)
        orderByParams = [orderByParams['orderByModel'],
            orderByParams['orderByAttribute'], orderByParams['orderByDirection']]
        orderByExpression = queryBuilder.getSQLAOrderBy(orderByParams, primaryKey)
        queryBuilder.clearErrors()
        return query.order_by(orderByExpression)
    else:
        model_ = getattr(model, queryBuilder.modelName)
        return query.order_by(asc(getattr(model_, primaryKey)))


################################################################################
# OLD model objects getters: for defaults and testing
################################################################################

def generateDefaultAdministrator(**kwargs):
    admin = model.User()
    admin.firstName = u'Admin'
    admin.lastName = u'Admin'
    admin.username = u'admin'
    admin.email = u'admin@example.com'
    admin.salt = generateSalt()
    admin.password = unicode(encryptPassword(u'adminA_1', str(admin.salt)))
    admin.role = u'administrator'
    admin.inputOrthography = None
    admin.outputOrthography = None
    admin.pageContent = u''
    createResearcherDirectory(admin, **kwargs)
    return admin

def generateDefaultContributor(**kwargs):
    contributor = model.User()
    contributor.firstName = u'Contributor'
    contributor.lastName = u'Contributor'
    contributor.username = u'contributor'
    contributor.email = u'contributor@example.com'
    contributor.salt = generateSalt()
    contributor.password = unicode(encryptPassword(u'contributorC_1', str(contributor.salt)))
    contributor.role = u'contributor'
    contributor.inputOrthography = None
    contributor.outputOrthography = None
    contributor.pageContent = u''
    createResearcherDirectory(contributor, **kwargs)
    return contributor

def generateDefaultViewer(**kwargs):
    viewer = model.User()
    viewer.firstName = u'Viewer'
    viewer.lastName = u'Viewer'
    viewer.username = u'viewer'
    viewer.email = u'viewer@example.com'
    viewer.salt = generateSalt()
    viewer.password = unicode(encryptPassword(u'viewerV_1', str(viewer.salt)))
    viewer.role = u'viewer'
    viewer.inputOrthography = None
    viewer.outputOrthography = None
    viewer.pageContent = u''
    createResearcherDirectory(viewer, **kwargs)
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
    return applicationSettings

def generateRestrictedTag():
    restrictedTag = model.Tag()
    restrictedTag.name = u'restricted'
    restrictedTag.description = u'''Forms tagged with the tag 'restricted'
can only be viewed by administrators, unrestricted users and the users they were
entered by.

Note: the restricted tag cannot be deleted and its name cannot be changed.
'''
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
phonetic and phonemic inventories.

Note: the foreign word tag cannot be deleted and its name cannot be changed.
'''
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
    speaker.pageContent = u'test speaker page content'
    return speaker

def generateDefaultUser():
    user = model.User()
    user.username = u'test user username'
    user.firstName = u'test user first name'
    user.lastName = u'test user last name'
    user.email = u'test user email'
    user.affiliation = u'test user affiliation'
    user.role = u'contributor'
    user.pageContent = u'test user page content'
    return user

def generateDefaultSource():
    source = model.Source()
    source.type = u'book'
    source.key = unicode(uuid4())
    source.author = u'test author'
    source.title = u'test title'
    source.publisher = u'Mouton'
    source.year = 1999
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

class State(object):
    """Empty class used to create a state instance with a 'full_dict' attribute
    that points to a dict of values being validated by a schema.  For example,
    the call to FormSchema().to_python in controllers/forms.py requires this
    State() instance as its second argument in order to make the inventory-based
    validators work correctly (see, e.g., ValidOrthographicTranscription).
    """
    pass

def getStateObject(values):
    """Return a State instance with some special attributes needed in the forms
    and oldcollections controllers.
    """
    state = State()
    state.full_dict = values
    state.user = session['user']
    return state

################################################################################
# Authorization Functions
################################################################################

def userIsAuthorizedToAccessModel(user, modelObject, unrestrictedUsers):
    """Return True if the user is authorized to access the model object.  Models
    tagged with the 'restricted' tag are only accessible to administrators, their
    enterers and unrestricted users.
    """
    if user.role == u'administrator':
        return True
    if isinstance(modelObject, (Form, File, Collection)):
        tags = modelObject.tags
        tagNames = [t.name for t in tags]
        entererId = modelObject.enterer_id
    else:
        modelBackupDict = modelObject.getDict()
        tags = modelBackupDict['tags']
        tagNames = [t['name'] for t in tags]
        entererId = modelBackupDict['enterer'].get('id', None)
    return not tags or \
        'restricted' not in tagNames or \
        user in unrestrictedUsers or \
        user.id == entererId


def userIsUnrestricted(user, unrestrictedUsers):
    """Return True if the user is an administrator, unrestricted or there is no
    restricted tag.
    """
    restrictedTag = getRestrictedTag()
    return not restrictedTag or user.role == u'administrator' or \
                                           user in unrestrictedUsers


def getUnrestrictedUsers():
    """Return the list of unrestricted users in
    app_globals.applicationSettings.applicationSettings.unrestrictedUsers.
    """
    return getattr(getattr(getattr(app_globals, 'applicationSettings', None),
                   'applicationSettings', None), 'unrestrictedUsers', [])


unauthorizedMsg = {'error': 'You are not authorized to access this resource.'}


def getRDBMSName(**kwargs):
    config = getConfig(**kwargs)
    try:
        SQLAlchemyURL = config['sqlalchemy.url']
        return SQLAlchemyURL.split(':')[0]
    except (TypeError, KeyError):
        # WARNING The exception below should be raised -- I've replaced it with this log just to allow Sphinx to import my controllers ...
        log.warn('The config object was inadequate.')
        #raise Exception('The config object was inadequate.')


################################################################################
# Some simple and ubiquitously used schemata
################################################################################

class PaginatorSchema(Schema):
    allow_extra_fields = True
    filter_extra_fields = False
    itemsPerPage = Int(not_empty=True, min=1)
    page = Int(not_empty=True, min=1)

class OrderBySchema(Schema):
    allow_extra_fields = True
    filter_extra_fields = False
    orderByModel = UnicodeString()
    orderByAttribute = UnicodeString()
    orderByDirection = OneOf([u'asc', u'desc'])

################################################################################
# File-specific data & functionality
################################################################################

allowedFileTypes = (
    #u'text/plain',
    #u'application/x-latex',
    #u'application/msword',
    #u'application/vnd.ms-powerpoint',
    #u'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    #u'application/vnd.oasis.opendocument.text',
    u'application/pdf',
    u'image/gif',
    u'image/jpeg',
    u'image/png',
    u'audio/mpeg',
    u'audio/ogg',
    u'audio/x-wav',
    u'video/mpeg',
    u'video/mp4',
    u'video/ogg',
    u'video/quicktime',
    u'video/x-ms-wmv'
)

def isAudioVideoFile(file_):
    return u'audio' in file_.MIMEtype or u'video' in file_.MIMEtype

utteranceTypes = (
    u'None',
    u'Object Language Utterance',
    u'Metalanguage Utterance',
    u'Mixed Utterance'
)

guess_type = guess_type

def clearDirectoryOfFiles(directoryPath):
    """Removes all files from the directory path but leaves the directory."""
    for fileName in os.listdir(directoryPath):
        if os.path.isfile(os.path.join(directoryPath, fileName)):
            os.remove(os.path.join(directoryPath, fileName))


################################################################################
# Collection-specific data & functionality
################################################################################

collectionTypes = (
    u'story',
    u'elicitation',
    u'paper',
    u'discourse',
    u'other'
)

# This is the regex for finding form references in the contents of collections.
formReferencePattern = re.compile('[Ff]orm\[([0-9]+)\]')

# This is the regex for finding collection references in the contents of collections.
#collectionReferencePattern = re.compile('[cC]ollection[\(\[](\d+)[\)\]]')
collectionReferencePattern = re.compile('[cC]ollection[\[\(](\d+)[\]\)]')

def rst2html(string):
    try:
        return publish_parts(string, writer_name='html')['html_body']
    except:
        return string

def md2html(string):
    try:
        return Markdown().convert(string)
    except:
        return string

markupLanguageToFunc = {
    'Markdown': md2html,
    'reStructuredText': rst2html
}

markupLanguages = markupLanguageToFunc.keys()

def getHTMLFromContents(contents, markupLanguage):
    return markupLanguageToFunc.get(markupLanguage, rst2html)(contents)


# Subject to change!  Or maybe these should be user-definable ...
syntacticCategoryTypes = (
    u'lexical',
    u'phrasal',
    u'sentential'
)

formStatuses = (u'tested', u'requires testing')

userRoles = (
    u'viewer',
    u'contributor',
    u'administrator'
)

def generateSalt():
    return unicode(uuid4().hex)

def encryptPassword(password, salt):
    """Use PassLib's pbkdf2 implementation to generate a hash from a password.
    Cf. http://packages.python.org/passlib/lib/passlib.hash.pbkdf2_digest.html#passlib.hash.pbkdf2_sha512
    """
    return pbkdf2_sha512.encrypt(password, salt=salt)

def generatePassword(length=12):
    lcLetters = string.letters[:26]
    ucLetters = string.letters[26:]
    digits = string.digits
    symbols = string.punctuation.replace('\\', '')
    password = [choice(lcLetters) for i in range(3)] + \
               [choice(ucLetters) for i in range(3)] + \
               [choice(digits) for i in range(3)] + \
               [choice(symbols) for i in range(3)]
    shuffle(password)
    return u''.join(password)


def getSearchParameters(queryBuilder):
    """Given an SQLAQueryBuilder instance, return (relative to the model being
    searched) the list of attributes and their aliases and licit relations
    relevant to searching.
    """
    return {
        'attributes': queryBuilder.schema[queryBuilder.modelName],
        'relations': queryBuilder.relations
    }


################################################################################
# Email Functionality
################################################################################

def getValueFromGmailConfig(gmailConfig, key, default=None):
    try:
        return gmailConfig.get('DEFAULT', key)
    except:
        return default

def getGmailConfig(**kwargs):
    config = getConfig(**kwargs)
    try:
        here = config['here']
    except (TypeError, KeyError):
        raise Exception('The config object was inadequate.')
    gmailConfigPath = os.path.join(here, 'gmail.ini')
    gmailConfig = ConfigParser.ConfigParser()
    try:
        gmailConfig.read(gmailConfigPath)
        return gmailConfig
    except ConfigParser.Error:
        return None

def getObjectLanguageId():
    return getattr(getApplicationSettings(), 'objectLanguageId', 'old')

def sendPasswordResetEmailTo(user, newPassword, **kwargs):
    """Send the "password reset" email to the user.  **kwargs should contain a
    config object (with 'config' as key) or a config file name (e.g.,
    'production.ini' with 'configFilename' as key).  If
    password_reset_smtp_server is set to smtp.gmail.com in the config file, then
    the email will be sent using smtp.gmail.com and the system will expect a
    gmail.ini file with valid gmail_from_address and gmail_from_password values.
    If the config file is test.ini and there is a test_email_to value, then that
    value will be the target of the email -- this allows testers to verify that
    an email is in fact being received.
    """

    to_address = user.email
    config = getConfig(**kwargs)
    if os.path.split(config['__file__'])[-1] == u'test.ini' and config.get('test_email_to'):
        to_address = config.get('test_email_to')
    password_reset_smtp_server = config.get('password_reset_smtp_server')
    languageId = getObjectLanguageId()
    from_address = '%s@old.org' % languageId
    appName = languageId.upper() + ' OLD' if languageId != 'old' else 'OLD'
    appURL = url('/', qualified=True)
    if password_reset_smtp_server == 'smtp.gmail.com':
        gmailConfig = getGmailConfig(config=config)
        from_address = getValueFromGmailConfig(gmailConfig, 'gmail_from_address')
        from_password = getValueFromGmailConfig(gmailConfig, 'gmail_from_password')
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(from_address, from_password)
    else:
        server = smtplib.SMTP('localhost')
    to_addresses = [to_address]
    message = u''.join([
        'From: %s <%s>\n' % (appName, from_address),
        'To: %s %s <%s>\n' % (user.firstName, user.lastName, to_address),
        'Subject: %s Password Reset\n\n' % appName,
        'Your password at %s has been reset to:\n\n    %s\n\n' % (appURL, newPassword),
        'Please change it once you have logged in.\n\n',
        '(Do not reply to this email.)'
    ])
    failures = server.sendmail(from_address, to_addresses, message)
    server.quit()
    return failures


def compile_query(query, **kwargs):
    """Return the SQLAlchemy query as a bona fide MySQL query.  Taken from
    http://stackoverflow.com/questions/4617291/how-do-i-get-a-raw-compiled-sql-query-from-a-sqlalchemy-expression.
    """

    RDBMSName = getRDBMSName(**kwargs)
    if RDBMSName == 'mysql':
        from sqlalchemy.sql import compiler
        from MySQLdb.converters import conversions, escape
        dialect = query.session.bind.dialect    # an object representing the dialect; dialect.name will be 'sqlite' or 'mysql'
        statement = query.statement     # The query as SQL with variable names instead of values, e.g., 'WHERE form.transcription like :transcription_1'
        comp = compiler.SQLCompiler(dialect, statement)
        enc = dialect.encoding
        params = []
        for k in comp.positiontup:
            v = comp.params[k]
            if isinstance(v, unicode):
                v = v.encode(enc)
            params.append( escape(v, conversions) )
        return (comp.string.encode(enc) % tuple(params)).decode(enc)
    else:
        return str(query)


################################################################################
# Command-line processes
################################################################################

def getSubprocess(command):
    """Return a subprocess process.  The command argument is a list.  See
    http://docs.python.org/2/library/subprocess.html
    """
    try:
        return Popen(command, stderr=PIPE, stdout=PIPE, stdin=PIPE)
    except OSError:
        return None

def commandLineProgramInstalled(command):
    """Command is the list representing the command-line utility."""
    try:
        return bool(getSubprocess(command))
    except:
        return False

def ffmpegInstalled():
    """Check if the ffmpeg command-line utility is installed on the host.  Check
    first if the answer to this question is cached in app_globals.
    """
    try:
        return app_globals.ffmpegInstalled
    except AttributeError:
        ffmpegInstalled = commandLineProgramInstalled(['ffmpeg'])
        app_globals.ffmpegInstalled = ffmpegInstalled
        return ffmpegInstalled

def ffmpegEncodes(format_):
    """Check if ffmpeg encodes the input format.  First check if it's installed."""
    if ffmpegInstalled():
        try:
            return app_globals.ffmpegEncodes[format_]
        except (AttributeError, KeyError):
            process = Popen(['ffmpeg', '-formats'], stderr=PIPE, stdout=PIPE)
            stdout, stderr = process.communicate()
            encodesFormat = 'E %s' % format_ in stdout
            try:
                app_globals.ffmpegEncodes[format_] = encodesFormat
            except AttributeError:
                app_globals.ffmpegEncodes = {format_: encodesFormat}
            return encodesFormat
    return False


################################################################################
# Eager loading of model queries
################################################################################

# It appears that SQLAlchemy does not query the db to retrieve a relational scalar
# when the foreign key id col value is NULL.  Therefore, eager loading on relational
# scalars is pointless if not wasteful.  However, collections that will always be
# accessed should always be eager loaded.

def eagerloadForm(query):
    return query.options(
        #subqueryload(model.Form.elicitor),
        subqueryload(model.Form.enterer),   # All forms *should* have enterers
        #subqueryload(model.Form.verifier),
        #subqueryload(model.Form.speaker),
        #subqueryload(model.Form.elicitationMethod),
        #subqueryload(model.Form.syntacticCategory),
        #subqueryload(model.Form.source),
        joinedload(model.Form.glosses),
        joinedload(model.Form.files),
        joinedload(model.Form.tags))

def eagerloadApplicationSettings(query):
    return query.options(
        #subqueryload(model.ApplicationSettings.inputOrthography),
        #subqueryload(model.ApplicationSettings.outputOrthography),
        #subqueryload(model.ApplicationSettings.storageOrthography)
    )

def eagerloadCollection(query):
    return query.options(
        #subqueryload(model.Collection.speaker),
        #subqueryload(model.Collection.elicitor),
        subqueryload(model.Collection.enterer),
        #subqueryload(model.Collection.source),
        subqueryload(model.Collection.forms),
        joinedload(model.Collection.tags),
        joinedload(model.Collection.files))

def eagerloadFile(query):
    return query.options(
        subqueryload(model.File.enterer),
        #subqueryload(model.File.elicitor),
        #subqueryload(model.File.speaker),
        joinedload(model.File.tags),
        joinedload(model.File.forms))

def eagerloadFormSearch(query):
    return query.options(subqueryload(model.FormSearch.searcher))

def eagerloadPhonology(query):
    return query.options(
        subqueryload(model.Phonology.enterer),
        subqueryload(model.Phonology.modifier))

def eagerloadUser(query):
    return query.options(
        #subqueryload(model.User.inputOrthography),
        #subqueryload(model.User.outputOrthography)
    )

def getUserFullName(user):
    return '%s %s' % (user.firstName, user.lastName)


def setAttr(obj, name, value, changed):
    """Set the value of obj.name to value only if obj.name != value.  Set changed
    to True if obj.name has changed as a result.  Return changed.  Useful in the
    updateModel function of the controllers.
    """
    if getattr(obj, name) != value:
        setattr(obj, name, value)
        changed = True
    return changed


validationValues = (u'None', u'Warning', u'Error')