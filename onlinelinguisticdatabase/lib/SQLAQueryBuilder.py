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

"""This module defines the SQLAQueryBuilder class.  An SQLAQueryBuilder instance
is used to build an SQLAlchemy query from a Python data structure (nested lists).

The two public methods are getSQLAQuery and getSQLAFilter.  Both take a list
representing a filter expression as input.  getSQLAQuery returns an SQLAlchemy
query object, including joins and filters.  getSQLAFilter returns an SQLAlchemy
filter expression and is called by getSQLAQuery.  Errors in the Python filter
expression will cause custom OLDSearchParseErrors to be raised.

The searchable models and their attributes (scalars & collections) are defined
in SQLAQueryBuilder.schema.

Simple filter expressions are lists with four or five items.  Complex filter
expressions are constructed via lists whose first element is one of the boolean
keywords 'and', 'or', 'not' and whose second element is a filter expression or
a list thereof (in the case of 'and' and 'or').  The examples below show a
filter expression accepted by SQLAQueryBuilder('Form').getSQLAQuery on the
second line followed by the equivalent SQLAlchemy ORM expression.  Note that the
target model of the SQLAQueryBuilder is set to 'Form' so all queries will be
against the Form model.

1. Simple scalar queries.
   ['Form', 'transcription', 'like', '%a%']
   Session.query(Form).filter(Form.transcription.like(u'%a%'))

2. Scalar relations.
   ['Form', 'enterer', 'firstName', 'regex', '^[JS]']
   Session.query(Form).filter(Form.enterer.has(User.firstName.op('regexp')(u'^[JS]')))

3. Scalar relations presence/absence.
   ['Form', 'enterer', '=', 'None']
   Session.query(Form).filter(Form.enterer==None)

4. Collection relations (w/ SQLA's collection.any() method).
   ['Form', 'files', 'id', 'in', [1, 2, 33, 5]]
   Session.query(Form).filter(Form.files.any(File.id.in_([1, 2, 33, 5])))

5. Collection relations (w/ joins; should return the same results as (4)).
   ['File', 'id', 'in', [1, 2, 33, 5]]
   fileAlias = aliased(File)
   Session.query(Form).filter(fileAlias.id.in_([1, 2, 33, 5])).outerjoin(fileAlias, Form.files)

6. Collection relations presence/absence.
   ['Form', 'files', '=', None]
   Session.query(Form).filter(Form.files == None)

7. Negation.
   ['not', ['Form', 'transcription', 'like', '%a%']]
   Session.query(Form).filter(not_(Form.transcription.like(u'%a%')))

8. Conjunction.
   ['and', [['Form', 'transcription', 'like', '%a%'],
            ['Form', 'elicitor', 'id', '=', 13]]]
   Session.query(Form).filter(and_(Form.transcription.like(u'%a%'),
                                   Form.elicitor.has(User.id==13)))

9. Disjunction.
   ['or', [['Form', 'transcription', 'like', '%a%'],
            ['Form', 'dateElicited', '<', '2012-01-01']]]
   Session.query(Form).filter(or_(Form.transcription.like(u'%a%'),
                                  Form.dateElicited < datetime.date(2012, 1, 1)))

10. Complex.
    ['and', [['Gloss', 'gloss', 'like', '%1%'],
            ['not', ['Form', 'morphemeBreak', 'regex', '[28][5-7]']],
            ['or', [['Form', 'datetimeModified', '<', '2012-03-01T00:00:00'],
                    ['Form', 'datetimeModified', '>', '2012-01-01T00:00:00']]]]]
    glossAlias = aliased(Gloss)
    Session.query(Form).filter(and_(
        glossAlias.gloss.like(u'%1%'),
        not_(Form.morphemeBreak.op('regexp')(u'[28][5-7]')),
        or_(
            Form.datetimeModified < ...,
            Form.datetimeModified > ...
        )
    )).outerjoin(glossAlias, Form.glosses)

Note also that SQLAQueryBuilder detects the RDBMS and issues collate commands
where necessary to ensure that pattern matches are case-sensitive while ordering
is not.

A further potential enhancement would be to allow doubly relational searches, e.g.,
return all forms whose enterer has remembered a form with a transcription like 'a':

xx. ['Form', 'enterer', 'rememberedForms', 'transcription', 'like', '%a%']
    Session.query(Form).filter(Form.enterer.has(User.rememberedForms.any(
        Form.transcription.like('%1%'))))

"""

import logging
import datetime
from sqlalchemy.sql import or_, and_, not_, asc, desc
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql.expression import collate
from sqlalchemy.orm import aliased
from sqlalchemy.types import Unicode, UnicodeText
from onlinelinguisticdatabase.lib.utils import normalize

log = logging.getLogger(__name__)


try:
    import simplejson as json
except ImportError:
    import json

try:
    import onlinelinguisticdatabase.model as old_model
    from onlinelinguisticdatabase.model.meta import Session
except ImportError:
    pass

try:
    from onlinelinguisticdatabase.lib.utils import getRDBMSName
except ImportError:
    def getRDBMSName():
        return 'sqlite'

try:
    from utils import datetimeString2datetime, dateString2date
except ImportError:
    # ImportError will be raised in utils if the Pylons environment is not
    # running, e.g., if we are debugging.  In this case, we need to define our
    # own date/datetime parseing functions.
    def datetimeString2datetime(datetimeString):
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
        try:
            return datetime.datetime.strptime(dateString, "%Y-%m-%d").date()
        except ValueError:
            return None

class OLDSearchParseError(Exception):
    def __init__(self, errors):
        self.errors = errors
    def __repr__(self):
        return '; '.join(['%s: %s' % (k, self.errors[k]) for k in self.errors])
    def __str__(self):
        return self.__repr__()
    def unpack_errors(self):
        return self.errors


class SQLAQueryBuilder(object):
    """SQLAQueryBuilder builds SQLAlchemy queries from Python data structures
    representing arbitrarily complex filter expressions.  Joins are inferred
    from the filter expression.  The public method most likely to be used is
    getSQLAQuery.  Example usage:
    
        > queryBuilder = SQLAlchemyQueryBuilder()
        > pythonQuery = [
            'and', [
                ['Gloss', 'gloss', 'like', '1'],
                ['not', ['Form', 'morphemeBreak', 'regex', '[28][5-7]']],
                ['or', [
                    ['Form', 'datetimeModified', '<', '2012-03-01T00:00:00'],
                    ['Form', 'datetimeModified', '>', '2012-01-01T00:00:00']]]]]
        > query = queryBuilder.getSQLAQuery(pythonQuery)
        > forms = query.all()
    """

    def __init__(self, modelName='Form', primaryKey='id', **kwargs):
        self.errors = {}
        self.joins = []
        self.modelName = modelName  # The name of the target model, i.e., the one we are querying, e.g., 'Form'
        self.primaryKey = primaryKey    # Some models have a primary key other than 'id' ...
        self.RDBMSName = getRDBMSName(**kwargs) # i.e., mysql or sqlite

    def getSQLAQuery(self, python):
        self.clearErrors()
        filterExpression = self.getSQLAFilter(python.get('filter'))
        orderByExpression = self._getSQLAOrderBy(python.get('orderBy'), self.primaryKey)
        self._raiseSearchParseErrorIfNecessary()
        query = self._getBaseQuery()
        query = query.filter(filterExpression)
        query = query.order_by(orderByExpression)
        query = self._addJoinsToQuery(query)
        return query

    def getSQLAFilter(self, python):
        """Return the SQLAlchemy filter expression generable by the input Python
        data structure or raise an OLDSearchParseError if the data structure is
        invalid.
        """
        return self._python2sqla(python)

    def getSQLAOrderBy(self, orderBy, primaryKey='id'):
        """The public method clears the errors and then calls the private method.
        This prevents interference from errors generated by previous orderBy calls.
        """
        self.clearErrors()
        return self._getSQLAOrderBy(orderBy, primaryKey)

    def _getSQLAOrderBy(self, orderBy, primaryKey='id'):
        """Input is an array of the form [<model>, <attribute>, <direction>];
        output is an SQLA order_by expression.
        """
        defaultOrderBy = asc(getattr(getattr(old_model, self.modelName), primaryKey))
        if orderBy is None:
            return defaultOrderBy
        try:
            modelName = self._getModelName(orderBy[0])
            attributeName = self._getAttributeName(orderBy[1], modelName)
            model = self._getModel(modelName)
            attribute = getattr(model, attributeName)
            if self.RDBMSName == 'sqlite' and attribute is not None and \
            isinstance(attribute.property.columns[0].type, self.SQLAlchemyStringTypes):
                attribute = collate(attribute, 'NOCASE')    # Force SQLite to order case-insensitively
            try:
                return {'asc': asc, 'desc': desc}.get(orderBy[2], asc)(attribute)
            except IndexError:
                return asc(attribute)
        except (IndexError, AttributeError):
            self._addToErrors('OrderByError', 'The provided order by expression was invalid.')
            return defaultOrderBy

    def clearErrors(self):
        self.errors = {}

    def _raiseSearchParseErrorIfNecessary(self):
        if self.errors:
            errors = self.errors.copy()
            self.clearErrors()    # Clear the errors so the instance can be reused to build further queries
            raise OLDSearchParseError(errors)

    def _getBaseQuery(self):
        queryModel = getattr(old_model, self.modelName)
        return Session.query(queryModel)

    def _addJoinsToQuery(self, query):
        for join in self.joins:
            query = query.outerjoin(join[0], join[1])
        self.joins = []
        return query

    def _python2sqla(self, python):
        """This is the function that is called recursively (if necessary) to
        build the SQLAlchemy filter expression.
        """
        try:
            if python[0] in ('and', 'or'):
                return {'and': and_, 'or': or_}[python[0]](
                    *[self._python2sqla(x) for x in python[1]])
            elif python[0] == 'not':
                return not_(self._python2sqla(python[1]))
            else:
                return self._getSimpleFilterExpression(*python)
        except TypeError, e:
            self.errors['Malformed OLD query error'] = u'The submitted query was malformed'
            self.errors['TypeError'] = e.__unicode__()
        except IndexError, e:
            self.errors['Malformed OLD query error'] = u'The submitted query was malformed'
            self.errors['IndexError'] = e.__unicode__()
        except Exception, e:
            self.errors['Malformed OLD query error'] = u'The submitted query was malformed'
            self.errors['Exception'] = e.__unicode__()

    SQLAlchemyStringTypes = (Unicode, UnicodeText)

    def _addToErrors(self, key, msg):
        self.errors[str(key)] = msg

    ############################################################################
    # Value converters
    ############################################################################

    def _getDateValue(self, dateString):
        """Converts ISO 8601 date strings to Python datetime.date objects."""
        if dateString is None:
            return dateString   # None can be used on date comparisons so assume this is what was intended
        date = dateString2date(dateString)
        if date is None:
            self._addToErrors('date %s' % str(dateString),
                u'Date search parameters must be valid ISO 8601 date strings.')
        return date

    def _getDatetimeValue(self, datetimeString):
        """Converts ISO 8601 datetime strings to Python datetime.datetime objects."""
        if datetimeString is None:
            return datetimeString   # None can be used on datetime comparisons so assume this is what was intended
        datetime = datetimeString2datetime(datetimeString)
        if datetime is None:
            self._addToErrors('datetime %s' % str(datetimeString),
                u'Datetime search parameters must be valid ISO 8601 datetime strings.')
        return datetime

    ############################################################################
    # Data structures
    ############################################################################
    # Alter the relations, schema and models2joins dicts in order to
    # change what types of input the query builder accepts.

    # The default set of available relations.  Relations with aliases are
    # treated as their aliases.  E.g., a search like ['Form', 'source_id' '=', ...]
    # will generate the filter model.Form.source_id.__eq__(...)
    relations = {
        '__eq__': {},
        '=': {'alias': '__eq__'},
        '__ne__': {},
        '!=': {'alias': '__ne__'},
        'like': {},
        'regexp': {},
        'regex': {'alias': 'regexp'},
        '__lt__': {},
        '<': {'alias': '__lt__'},
        '__gt__': {},
        '>': {'alias': '__gt__'},
        '__le__': {},
        '<=': {'alias': '__le__'},
        '__ge__': {},
        '>=': {'alias': '__ge__'},
        'in_': {},
        'in': {'alias': 'in_'}
    }

    equalityRelations = {
        '__eq__': {},
        '=': {'alias': '__eq__'},
        '__ne__': {},
        '!=': {'alias': '__ne__'}
    }

    # The schema attribute describes the database structure in a way that allows
    # the query builder to properly interpret the list-based queries and generate
    # errors where necessary.  Maps model names to attribute names.  Attribute names whose values contain
    # an 'alias' key are treated as the value of that key, e.g., ['Form',
    # 'enterer' ...] will be treated as Form.enterer_id...  The relations listed
    # in self.relations above are the default for all attributes.  This can be
    # overridden by specifying a 'relation' key (cf.
    # schema['Form']['glosses'] below).  Certain attributes require
    # value converters -- functions that change the value in some attribute-
    # specific way, e.g., conversion of ISO 8601 datetimes to Python datetime
    # objects.
    schema = {
        'Collection': {
            'id': {},
            'UUID': {},
            'title': {},
            'type': {},
            'url': {},
            'description': {},
            'markupLanguage': {},
            'contents': {},
            'html': {},
            'speaker': {'foreignModel': 'Speaker', 'type': 'scalar'},
            'source': {'foreignModel': 'Source', 'type': 'scalar'},
            'elicitor': {'foreignModel': 'User', 'type': 'scalar'},
            'enterer': {'foreignModel': 'User', 'type': 'scalar'},
            'dateElicited': {'valueConverter': '_getDateValue'},
            'datetimeEntered': {'valueConverter': '_getDatetimeValue'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'tags': {'foreignModel': 'Tag', 'type': 'collection'},
            'forms': {'foreignModel': 'Form', 'type': 'collection'},
            'files': {'foreignModel': 'File', 'type': 'collection'}
        },
        'CollectionBackup': {
            'id': {},
            'UUID': {},
            'collection_id': {},
            'title': {},
            'type': {},
            'url': {},
            'description': {},
            'markupLanguage': {},
            'contents': {},
            'html': {},
            'speaker': {},
            'source': {},
            'elicitor': {},
            'enterer': {},
            'dateElicited': {'valueConverter': '_getDateValue'},
            'datetimeEntered': {'valueConverter': '_getDatetimeValue'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'tags': {},
            'forms': {},
            'files': {}
        },
        'ElicitationMethod': {
            'id': {},
            'name': {},
            'description': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
        },
        'Form': {
            'id': {},
            'UUID': {},
            'transcription': {},
            'phoneticTranscription': {},
            'narrowPhoneticTranscription': {},
            'morphemeBreak': {},
            'morphemeGloss': {},
            'comments': {},
            'speakerComments': {},
            'grammaticality': {},
            'dateElicited': {'valueConverter': '_getDateValue'},
            'datetimeEntered': {'valueConverter': '_getDatetimeValue'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'syntacticCategoryString': {},
            'morphemeBreakIDs': {},
            'morphemeGlossIDs': {},
            'breakGlossCategory': {},
            'syntax': {},
            'semantics': {},
            'elicitor': {'foreignModel': 'User', 'type': 'scalar'},
            'enterer': {'foreignModel': 'User', 'type': 'scalar'},
            'verifier': {'foreignModel': 'User', 'type': 'scalar'},
            'speaker': {'foreignModel': 'Speaker', 'type': 'scalar'},
            'elicitationMethod': {'foreignModel': 'ElicitationMethod', 'type': 'scalar'},
            'syntacticCategory': {'foreignModel': 'SyntacticCategory', 'type': 'scalar'},
            'source': {'foreignModel': 'Source', 'type': 'scalar'},
            'glosses': {'foreignModel': 'Gloss', 'type': 'collection'},
            'tags': {'foreignModel': 'Tag', 'type': 'collection'},
            'files': {'foreignModel': 'File', 'type': 'collection'},
            'collections': {'foreignModel': 'Collection', 'type': 'collection'}
        },
        'FormBackup': {
            'id': {},
            'UUID': {},
            'form_id': {},
            'transcription': {},
            'phoneticTranscription': {},
            'narrowPhoneticTranscription': {},
            'morphemeBreak': {},
            'morphemeGloss': {},
            'comments': {},
            'speakerComments': {},
            'grammaticality': {},
            'dateElicited': {'valueConverter': '_getDateValue'},
            'datetimeEntered': {'valueConverter': '_getDatetimeValue'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'syntacticCategoryString': {},
            'morphemeBreakIDs': {},
            'morphemeGlossIDs': {},
            'breakGlossCategory': {},
            'syntax': {},
            'semantics': {},
            'elicitor': {},
            'enterer': {},
            'verifier': {},
            'speaker': {},
            'elicitationMethod': {},
            'syntacticCategory': {},
            'source': {},
            'glosses': {},
            'tags': {},
            'files': {},
            'collections': {}
        },
        'FormSearch': {
            'id': {},
            'name': {},
            'search': {},
            'description': {},
            'enterer': {'foreignModel': 'User', 'type': 'scalar'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'File': {
            'id': {},
            'filename': {},
            'name': {},
            'MIMEtype': {},
            'size': {},
            'enterer': {'foreignModel': 'User', 'type': 'scalar'},
            'description': {},
            'dateElicited': {'valueConverter': '_getDateValue'},
            'datetimeEntered': {'valueConverter': '_getDatetimeValue'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'elicitor': {'foreignModel': 'User', 'type': 'scalar'},
            'speaker': {'foreignModel': 'Speaker', 'type': 'scalar'},
            'parentFile': {'foreignModel': 'File', 'type': 'scalar'},
            'utteranceType': {},
            'start': {},
            'end': {},
            'url': {},
            'password': {},
            'tags': {'foreignModel': 'Tag', 'type': 'collection'},
            'forms': {'foreignModel': 'Collection', 'type': 'collection'},
            'collections': {'foreignModel': 'Collection', 'type': 'collection'}
        },
        'Gloss': {
            'id': {},
            'gloss': {},
            'glossGrammaticality': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'Language': {
            'Id': {},
            'Part2B': {},
            'Part2T': {},
            'Part1': {},
            'Scope': {},
            'Type': {},
            'Ref_Name': {},
            'Comment': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'Memorizer': {
            'id': {},
            'firstName': {},
            'lastName': {},
            'role': {}
        },
        'Orthography': {
            'id': {},
            'name': {},
            'orthography': {},
            'lowercase': {},
            'initialGlottalStops': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'Source': {
            'id': {},
            'file_id': {},
            'file': {'foreignModel': 'File', 'type': 'scalar'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'type': {},
            'key': {},
            'address': {},
            'annote': {},
            'author': {},
            'booktitle': {},
            'chapter': {},
            'crossref': {},
            'edition': {},
            'editor': {},
            'howpublished': {},
            'institution': {},
            'journal': {},
            'keyField': {},
            'month': {},
            'note': {},
            'number': {},
            'organization': {},
            'pages': {},
            'publisher': {},
            'school': {},
            'series': {},
            'title': {},
            'typeField': {},
            'url': {},
            'volume': {},
            'year': {},
            'affiliation': {},
            'abstract': {},
            'contents': {},
            'copyright': {},
            'ISBN': {},
            'ISSN': {},
            'keywords': {},
            'language': {},
            'location': {},
            'LCCN': {},
            'mrnumber': {},
            'price': {},
            'size': {}
        },
        'Speaker': {
            'id': {},
            'firstName': {},
            'lastName': {},
            'dialect': {},
            'pageContent': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'SyntacticCategory': {
            'id': {},
            'name': {},
            'type': {},
            'description': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'User': {
            'id': {},
            'firstName': {},
            'lastName': {},
            'email': {},
            'affiliation': {},
            'role': {},
            'markupLanguage': {},
            'pageContent': {},
            'html': {},
            'inputOrthography': {'foreignModel': 'Orthography', 'type': 'scalar'},
            'outputOrthography': {'foreignModel': 'Orthography', 'type': 'scalar'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'rememberedForms': {'foreignModel': 'Form', 'type': 'collection'}
        },
        'Tag': {
            'id': {},
            'name': {},
            'description': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        }
    }

    modelAliases = {
        'Memorizer': 'User'
    }

    # Maps model names to the names of other models they can be joined to for
    # queries.  The values of the join models are the attributes of the original
    # model that the joins are actually made on, e.g., outerjoin(model.Form.tags)
    models2joins = {
        'Form': {
            'File': 'files',
            'Gloss': 'glosses',
            'Tag': 'tags',
            'Collection': 'collections',
            'Memorizer': 'memorizers'
        },
        'File': {
            'Tag': 'tags',
            'Form': 'forms',
            'Collection': 'collections'
        },
        'Collection': {
            'Form': 'forms',
            'File': 'files',
            'Tag': 'tags'
        }
    }

    ############################################################################
    # Model getters
    ############################################################################

    def _getModelName(self, modelName):
        """Always return modelName; store an error if modelName is invalid."""
        if modelName not in self.schema:
            self._addToErrors(modelName, u'Searching on the %s model is not permitted' % modelName)
        return modelName

    def _getModel(self, modelName, addToJoins=True):
        try:
            model = getattr(old_model, self.modelAliases.get(modelName, modelName))
        except AttributeError:
            model = None
            self._addToErrors(modelName, u"The OLD has no model %s" % modelName)

        # Store any implicit joins in self.joins to await addition to the query
        # in self._addJoinsToQuery.  Using sqlalchemy.orm's aliased to alias
        # models/tables is what permits filters on multiple -to-many relations.
        # Aliasing File while searching Form.files, for example, permits us to
        # retrieve all forms that are associated to file 71 and file 74.
        if addToJoins and modelName != self.modelName:
            joinModels = self.models2joins.get(self.modelName, {})
            if modelName in joinModels:
                joinCollectionName = joinModels[modelName]
                joinCollection = getattr(getattr(old_model, self.modelName),
                                        joinCollectionName)
                model = aliased(model)
                self.joins.append((model, joinCollection))
            else:
                self._addToErrors(modelName,
                    u"Searching the %s model by joining on the %s model is not possible" % (
                        self.modelName, modelName))
        return model

    def _getAttributeModelName(self, attributeName, modelName):
        """Returns the name of the model X that stores the data for the attribute
        A of model M, e.g., the attributeModelName for modelName='Form' and
        attributeName='enterer' is 'User'.
        """
        attributeDict = self._getAttributeDict(attributeName, modelName)
        try:
            return attributeDict['foreignModel']
        except KeyError:
            self._addToErrors(u'%s.%s' % (modelName, attributeName),
                u'The %s attribute of the %s model does not represent a many-to-one relation.' % (
                    attributeName, modelName))
        except:
            pass    # probably a TypeError, meaning modelName.attributeName is invalid; would have already been caught

    ############################################################################
    # Attribute getters
    ############################################################################

    def _getAttributeName(self, attributeName, modelName):
        """Return attributeName or cache an error if attributeName is not in
        self.schema[modelName].
        """
        attributeDict = self._getAttributeDict(attributeName, modelName, True)
        return attributeName

    def _getAttributeDict(self, attributeName, modelName, reportError=False):
        """Return the dict needed to validate a given attribute of a given model,
        or return None.  Propagate an error (optionally) if the attributeName is
        invalid.
        """
        attributeDict = self.schema.get(modelName, {}).get(
            attributeName, None)
        if attributeDict is None and reportError:
            self._addToErrors('%s.%s' % (modelName, attributeName),
                u'Searching on %s.%s is not permitted' % (modelName, attributeName))
        return attributeDict

    def _getAttribute(self, attributeName, model, modelName):
        try:
            attribute = self._collateAttribute(getattr(model, attributeName))
        except AttributeError:  # model can be None
            attribute = None
            self._addToErrors('%s.%s' % (modelName, attributeName),
                u"There is no attribute %s of %s" % (attributeName, modelName))
        return attribute

    def _collateAttribute(self, attribute):
        """Append a MySQL COLLATE utf8_bin expression after the column name, if
        appropriate.  This allows regexp and like searches to be case-sensitive.
        An example SQLA query would be Session.query(model.Form).filter(
        collate(model.Form.transcription, 'utf8_bin').like(u'a%'))
        
        Previously there was a condition on collation that the relationName be in
        ('like', 'regexp').  This condition was removed because MySQL does case-
        insensitive equality searches too!
        """
        if self.RDBMSName == 'mysql' and attribute is not None:
            try:
                attributeType = attribute.property.columns[0].type
            except AttributeError:
                attributeType = None
            if isinstance(attributeType, self.SQLAlchemyStringTypes):
                attribute = collate(attribute, 'utf8_bin')
        return attribute

    ############################################################################
    # Relation getters
    ############################################################################

    def _getRelationName(self, relationName, modelName, attributeName):
        """Return relationName or its alias; propagate an error if relationName is invalid."""
        relationDict = self._getRelationDict(relationName, modelName, attributeName, True)
        try:
            return relationDict.get('alias', relationName)
        except AttributeError:  # relationDict can be None
            return None

    def _getRelationDict(self, relationName, modelName, attributeName, reportError=False):
        attributeRelations = self._getAttributeRelations(attributeName, modelName)
        try:
            relationDict = attributeRelations.get(relationName, None)
        except AttributeError:
            relationDict = None
        if relationDict is None and reportError:
            self._addToErrors('%s.%s.%s' % (modelName, attributeName, relationName),
                u"The relation %s is not permitted for %s.%s" % (relationName, modelName, attributeName))
        return relationDict

    def _getAttributeRelations(self, attributeName, modelName):
        """Return the data structure encoding what relations are valid for the
        input attribute name.
        """
        attributeDict = self._getAttributeDict(attributeName, modelName)
        try:
            if attributeDict.get('foreignModel'):
                return self.equalityRelations
            else:
                return self.relations
        except AttributeError:  # attributeDict can be None
            return None

    def _getRelation(self, relationName, attribute, attributeName, modelName):
        try:
            if relationName == 'regexp':
                op = getattr(attribute, 'op')
                relation = op('regexp')
            else:
                relation = getattr(attribute, relationName)
        except AttributeError:  # attribute can be None
            relation = None
            self._addToErrors('%s.%s.%s' % (modelName, attributeName, relationName),
                u"There is no relation '%s' of '%s.%s'" % (relationName, modelName, attributeName))
        return relation

    ############################################################################
    # Value getters
    ############################################################################

    def _normalize(self, value):
        def normalizeIfString(value):
            if type(value) in (str, unicode):
                return normalize(value)
            return value
        value = normalizeIfString(value)
        if type(value) is list:
            value = [normalizeIfString(i) for i in value]
        return value

    def _getValueConverter(self, attributeName, modelName):
        attributeDict = self._getAttributeDict(attributeName, modelName)
        try:
            valueConverterName = attributeDict.get('valueConverter', '')
            return getattr(self, valueConverterName, None)
        except AttributeError:  # attributeDict can be None
            return None

    def _getValue(self, value, modelName, attributeName, relationName):
        """Unicode normalize & modify the value using a valueConverter (if necessary)."""
        value = self._normalize(value)    # unicode normalize (NFD) search patterns; we might want to parameterize this
        valueConverter = self._getValueConverter(attributeName, modelName)
        if valueConverter is not None:
            if type(value) is type([]):
                value = [valueConverter(li) for li in value]
            else:
                value = valueConverter(value)
        return value

    ############################################################################
    # Filter expression getters
    ############################################################################

    def _getInvalidFilterExpressionMessage(self, modelName, attributeName,
                                          relationName, value):
        return u"Invalid filter expression: %s.%s.%s(%s)" % (modelName,
                                            attributeName, relationName, repr(value))

    def _getInvalidModelAttributeErrors(self, relation, value, modelName,
            attributeName, relationName, attribute, attributeModelName, attributeModelAttributeName):
        """Avoid catching a (costly) RuntimeError by preventing _getFilterExpression
        from attempting to build relation(value) or attribute.has(relation(value)).
        We do this by returning a non-empty list of error tuples if Model.attribute
        errors are present in self.errors.
        """
        e = []
        if attributeModelName:
            errorKey = '%s.%s' % (attributeModelName, attributeModelAttributeName)
            if self.errors.get(errorKey) == u'Searching on the %s is not permitted' % errorKey:
                e.append(('%s.%s.%s' % (attributeModelName, attributeModelAttributeName, relationName),
                    self._getInvalidFilterExpressionMessage(attributeModelName,
                            attributeModelAttributeName, relationName, value)))
        errorKey = '%s.%s' % (modelName, attributeName)
        if self.errors.get(errorKey) == u'Searching on %s is not permitted' % errorKey:
            e.append(('%s.%s.%s' % (modelName, attributeName, relationName),
                self._getInvalidFilterExpressionMessage(modelName, attributeName,
                                                        relationName, value)))
        return e

    def _getMetaRelation(self, attribute, modelName, attributeName):
        """Return the has() or the any() method of the input attribute, depending
        on the value of schema[modelName][attributeName]['type'].
        """
        return getattr(attribute, {'scalar': 'has', 'collection': 'any'}[
            self.schema[modelName][attributeName]['type']])

    def _getFilterExpression(self, relation, value, modelName, attributeName,
                             relationName, attribute=None, attributeModelName=None,
                             attributeModelAttributeName=None):
        """Attempt to return relation(value), catching and storing errors as
        needed.  If 5 args are provided, we are doing a [mod, attr, rel, val]
        search; if all 8 are provided, it's a [mod, attr, attrModAttr, rel, val]
        one.
        """
        invalidModelAttributeErrors = self._getInvalidModelAttributeErrors(
            relation, value, modelName, attributeName, relationName, attribute,
            attributeModelName, attributeModelAttributeName)
        if invalidModelAttributeErrors:
            filterExpression = None
            for e in invalidModelAttributeErrors:
                self._addToErrors(e[0], e[1])
        else:
            try:
                if attributeModelName:
                    metaRelation = self._getMetaRelation(attribute, modelName, attributeName)
                    filterExpression = metaRelation(relation(value))
                else:
                    filterExpression = relation(value)
            except AttributeError:
                filterExpression = None
                self._addToErrors('%s.%s' % (modelName, attributeName),
                    u'The %s.%s attribute does not represent a many-to-one relation.' % (
                        modelName, attributeName))
            except TypeError:
                filterExpression = None
                self._addToErrors('%s.%s.%s' % (modelName, attributeName, relationName),
                    self._getInvalidFilterExpressionMessage(modelName,
                                            attributeName, relationName, value))
            except InvalidRequestError, e:
                filterExpression = None
                self.errors['InvalidRequestError'] = e.__unicode__()
            except OperationalError, e:
                filterExpression = None
                self.errors['OperationalError'] = e.__unicode__()
            except RuntimeError, e:
                filterExpression = None
                self.errors['RuntimeError'] = e.__unicode__()
        return filterExpression

    def _getSimpleFilterExpression(self, *args):
        """Build an SQLAlchemy filter expression.  Examples:

        1. ['Form', 'transcription', '=', 'abc'] =>
           model.Form.transcription.__eq__('abc')

        2. ['Form', 'enterer', 'firstName', 'like', 'J%'] =>
           Session.query(model.Form)\
                .filter(model.Form.enterer.has(model.User.firstName.like(u'J%')))

        3. ['Tag', 'name', 'like', '%abc%'] (when searching the Form model) =>
           aliasedTag = aliased(model.Tag)
           Session.query(model.Form)\
                .filter(aliasedTag.name.like(u'%abc%'))\
                .outerjoin(aliasedTag, model.Form.tags)

        4. ['Form', 'tags', 'name', 'like', '%abc%'] =>
           Session.query(model.Form)\
                .filter(model.Form.tags.any(model.Tag.name.like(u'%abc%')))
        """
        modelName = self._getModelName(args[0])
        attributeName = self._getAttributeName(args[1], modelName)
        if len(args) == 4:
            model = self._getModel(modelName)
            relationName = self._getRelationName(args[2], modelName, attributeName)
            value = self._getValue(args[3], modelName, attributeName, relationName)
            attribute = self._getAttribute(attributeName, model, modelName)
            relation = self._getRelation(relationName, attribute, attributeName, modelName)
            return self._getFilterExpression(relation, value, modelName, attributeName, relationName)
        else:
            attributeModelName = self._getAttributeModelName(attributeName, modelName)
            attributeModelAttributeName = self._getAttributeName(args[2], attributeModelName)
            relationName = self._getRelationName(args[3], attributeModelName, attributeModelAttributeName)
            value = self._getValue(args[4], attributeModelName, attributeModelAttributeName, relationName)
            model = self._getModel(modelName, False)
            attribute = self._getAttribute(attributeName, model, modelName)
            attributeModel = self._getModel(attributeModelName, False)
            attributeModelAttribute = self._getAttribute(attributeModelAttributeName, attributeModel, attributeModelName)
            relation = self._getRelation(relationName, attributeModelAttribute, attributeModelAttributeName, attributeModelName)
            return self._getFilterExpression(relation, value, modelName, attributeName, relationName,
                                             attribute, attributeModelName, attributeModelAttributeName)