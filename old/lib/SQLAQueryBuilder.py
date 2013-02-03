"""This module defines the SQLAQueryBuilder class.  An SQLAQueryBuilder instance
is used to build an SQLAlchemy query from a Python data structure (nested lists).

The two public methods are getSQLAQuery and getSQLAFilter.  Both take a list
representing a filter expression as input.  getSQLAQuery returns an SQLAlchemy
query object, including joins and filters.  getSQLAFilter returns an SQLAlchemy
filter expression and is called by getSQLAQuery.  Errors in the Python filter
expression will cause custom OLDSearchParseErrors to be raised.

The Python data structure from which the SQLA filter expression is built and the
joins deduced, is expressible via the following context free grammar.

Terminals = {'not', 'and', 'or'}
Nonterminals: {Model, Attribute, Relation, Value, SimpleFilterExpression, ComplexFilterExpression}
S: ComplexFilterExpression
P: Model -> {x | x is a searchable model name}
   Attribute -> {x | x is a searchable attribute of the relevant model}
   Relation -> {x | x is a valid relation for the model attribute being searched}
   Value -> {x | x is a sensible value for a relation-type search on the relevant model attribute}
   SimpleFilterExpression -> [Model, Attribute, Relation, Value]
   ComplexFilterExpression -> SimpleFilterExpression |
                              ['not', ComplexFilterExpression] |
                              [('or'|'and), [ComplexFilterExpression*]]

Some illustrative examples follow.  Note that queries of any level of complexity
should be possible.

1. ['Form', 'transcription', 'like', 'abc']
2. ['not', ['Form', 'transcription', 'like', 'abc']]
3. ['and', [['Form', 'transcription', 'like', 'abc'],
            ['Form', 'elicitor', '=', 13]]]
4. ['or', [['Form', 'transcription', 'like', 'abc'],
            ['Form', 'dateElicited', '<', '2012-01-01']]]
5. ['and', [['Gloss', 'gloss', 'like', '1'],
            ['not', ['Form', 'morphemeBreak', 'regex', '[28][5-7]']],
            ['or', [['Form', 'datetimeModified', '<', '2012-03-01T00:00:00'],
                    ['Form', 'datetimeModified', '>', '2012-01-01T00:00:00']]]]]

The SQLAQueryBuilder constructor takes a model name as its first argument.  This
references the type of models wanted in the result.  If a simple filter
expression references a different model, an outer join is implied and will be
added to the query returned by getSQLAQuery.  For example, the query expression
in (5) above will cause getSQLAQuery to add an outer join on Form.glosses.
"""

import logging
import datetime
from sqlalchemy.sql import or_, and_, not_, asc, desc
from sqlalchemy.exc import OperationalError, InvalidRequestError
from sqlalchemy.sql.expression import collate
from sqlalchemy.orm import aliased
from sqlalchemy.types import Unicode, UnicodeText
from old.lib.utils import normalize

log = logging.getLogger(__name__)


try:
    import simplejson as json
except ImportError:
    import json

try:
    import old.model as old_model
    from old.model.meta import Session
except ImportError:
    pass

try:
    from old.lib.utils import getRDBMSName
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

    def __init__(self, modelName='Form', primaryKey='id', mode='production', **kwargs):
        self.errors = {}
        self.joins = []
        self.modelName = modelName  # The name of the target model, i.e., the one we are querying, e.g., 'Form'
        self.primaryKey = primaryKey    # Some models have a primary key other than 'id' ...
        self.mode = mode            # i.e., production or development
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
        if self.mode == u'production':
            return self._python2sqla(python)
        else:
            return self._python2sqla_debug(python)

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

    def _python2sqla_debug(self, python):
        """If self.mode is set to 'debug', this is called instead of _python2sqla."""
        try:
            if python[0] in ('and', 'or'):
                return '%s_()' % (python[0], ', '.join([self._python2sqla_debug(x) for x in python[1]]))
            elif python[0] == 'not':
                return 'not_(%s)' % self._python2sqla_debug(python[1])
            else:
                return self._getSimpleFilterExpression(*python)
        except TypeError, e:
            self.errors['Malformed OLD query error'] = u'The submitted query was malformed'
            self.errors['IndexError'] = e.__unicode__()
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
    # Alter the relations, models2attributes and models2joins dicts in order to
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

    # Maps model names to attribute names.  Attribute names whose values contain
    # an 'alias' key are treated as the value of that key, e.g., ['Form',
    # 'enterer' ...] will be treated as Form.enterer_id...  The relations listed
    # in self.relations above are the default for all attributes.  This can be
    # overridden by specifying a 'relation' key (cf.
    # models2attributes['Form']['glosses'] below).  Certain attributes require
    # value converters -- functions that change the value in some attribute-
    # specific way, e.g., conversion of ISO 8601 datetimes to Python datetime
    # objects.
    models2attributes = {
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
            'elicitor': {'alias': 'elicitor_id'},
            'elicitor_id': {},
            'enterer': {'alias': 'enterer_id'},
            'enterer_id': {},
            'verifier': {'alias': 'verifier_id'},
            'verifier_id': {},
            'speaker': {'alias': 'speaker_id'},
            'speaker_id': {},
            'elicitationMethod': {'alias': 'elicitationmethod_id'},
            'elicitationmethod_id': {},
            'syntacticCategory': {'alias': 'syntacticcategory_id'},
            'syntacticcategory_id': {},
            'source': {'alias': 'source_id'},
            'source_id': {},
            'glosses': {'relations': equalityRelations},
            'tags': {'relations': equalityRelations},
            'files': {'relations': equalityRelations},
            'collections': {'relations': equalityRelations}
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
        'File': {
            'id': {},
            'filename': {},
            'name': {},
            'MIMEtype': {},
            'size': {},
            'enterer': {'alias': 'enterer_id'},
            'enterer_id': {},
            'description': {},
            'dateElicited': {'valueConverter': '_getDateValue'},
            'datetimeEntered': {'valueConverter': '_getDatetimeValue'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'elicitor': {'alias': 'elicitor_id'},
            'elicitor_id': {},
            'speaker': {'alias': 'speaker_id'},
            'speaker_id': {},
            'parentFile': {'alias': 'parentFile_id'},
            'parentFile_id': {},
            'utteranceType': {},
            'start': {},
            'end': {},
            'embeddedFileMarkup': {},
            'embeddedFilePassword': {},
            'tags': {'relations': equalityRelations},
            'forms': {'relations': equalityRelations},
            'collections': {'relations': equalityRelations}
        },
        'Gloss': {
            'id': {},
            'gloss': {},
            'glossGrammaticality': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'Tag': {
            'id': {},
            'name': {},
            'description': {},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
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
            'speaker': {'alias': 'speaker_id'},
            'speaker_id': {},
            'source': {'alias': 'source_id'},
            'source_id': {},
            'elicitor': {'alias': 'elicitor_id'},
            'elicitor_id': {},
            'enterer': {'alias': 'enterer_id'},
            'enterer_id': {},
            'dateElicited': {'valueConverter': '_getDateValue'},
            'datetimeEntered': {'valueConverter': '_getDatetimeValue'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'},
            'tags': {'relations': equalityRelations},
            'forms': {'relations': equalityRelations},
            'files': {'relations': equalityRelations}
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
        'Source': {
            'id': {},
            'file_id': {},
            'file': {'alias': 'file_id'},
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
        'FormSearch': {
            'id': {},
            'name': {},
            'search': {},
            'description': {},
            'enterer_id': {},
            'enterer': {'alias': 'enterer_id'},
            'datetimeModified': {'valueConverter': '_getDatetimeValue'}
        },
        'Memorizer': {
            'id': {},
            'firstName': {},
            'lastName': {},
            'role': {}
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
        if modelName not in self.models2attributes:
            self._addToErrors(modelName, u'Searching on the %s model is not permitted' % modelName)
        return modelName

    def _getModel(self, modelName):
        try:
            model = getattr(old_model, self.modelAliases.get(modelName, modelName))
        except AttributeError:
            model = None
            self._addToErrors(modelName, u"The OLD has no model %s" % modelName)

        # Store any implicit joins in self.joins to await addition to the query
        # in self._addJoinsToQuery.  Using sqlalchemy.orm's aliased to alias
        # models/tables is what permits filters on multiple -to-many relations,
        # e.g., has both tags X and Y.
        if modelName != self.modelName:
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

    ############################################################################
    # Attribute getters
    ############################################################################

    def _getAttributeName(self, attributeName, modelName):
        """Return attributeName or its alias; store an error if attributeName is invalid."""
        attributeDict = self._getAttributeDict(attributeName, modelName, True)
        try:
            return attributeDict.get('alias', attributeName)
        except AttributeError:  # attributeDict can be None
            return attributeName

    def _getAttributeDict(self, attributeName, modelName, reportError=False):
        """Return the dict needed to validate a given attribute of a given model,
        or return None.  Propagate an error (optionally) if the attributeName is
        invalid.
        """
        attributeDict = self.models2attributes.get(modelName, {}).get(
            attributeName, None)
        if attributeDict is None and reportError:
            self._addToErrors('%s.%s' % (modelName, attributeName),
                u'Searching on %s.%s is not permitted' % (modelName, attributeName))
        return attributeDict

    def _getAttribute(self, attributeName, model, modelName, relationName):
        try:
            attribute = self._collateAttribute(relationName,
                                               getattr(model, attributeName))
        except AttributeError:  # model can be None
            attribute = None
            self._addToErrors('%s.%s' % (modelName, attributeName),
                u"There is no attribute %s of %s" % (attributeName, modelName))
        return attribute

    def _collateAttribute(self, relationName, attribute):
        """Append a MySQL COLLATE utf8_bin expression after the column name, if
        appropriate.  This allows regexp and like searches to be case-sensitive.
        An example SQLA query would be Session.query(model.Form).filter(
        collate(model.Form.transcription, 'utf8_bin').like(u'a%'))
        
        An additional condition on collation was that the relationName be in
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
            return attributeDict.get('relations', self.relations)
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

    def _getFilterExpression(self, relation, value, modelName, attributeName, relationName):
        """Attempt to return relation(value), catching and storing errors as needed."""
        # Avoid catching a (costly) RuntimeError by inspecting our own error cache.
        if self.errors.get('%s.%s' % (modelName, attributeName)) == \
        u'Searching on %s.%s is not permitted' % (modelName, attributeName):
            filterExpression = None
            self._addToErrors('%s.%s.%s' % (modelName, attributeName, relationName),
                self._getInvalidFilterExpressionMessage(modelName, attributeName, relationName, value))
        else:
            try:
                filterExpression = relation(value)
            except TypeError:
                filterExpression = None
                self._addToErrors('%s.%s.%s' % (modelName, attributeName, relationName),
                    self._getInvalidFilterExpressionMessage(modelName, attributeName, relationName, value))
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

    def _getSimpleFilterExpression(self, modelName, attributeName, relationName,
                                   valueLiteral):
        """Build an SQLAlchemy filter expressions, e.g., from ['Form',
        'transcription', '=', 'abc'] return model.Form.transcription.__eq__('abc').
        """
        modelName = self._getModelName(modelName)
        attributeName = self._getAttributeName(attributeName, modelName)
        relationName = self._getRelationName(relationName, modelName, attributeName)
        value = self._getValue(valueLiteral, modelName, attributeName, relationName)
        if self.mode == 'production':
            model = self._getModel(modelName)
            attribute = self._getAttribute(attributeName, model, modelName, relationName)
            relation = self._getRelation(relationName, attribute, attributeName, modelName)
            return self._getFilterExpression(relation, value,
                                    modelName, attributeName, relationName)
        else:
            return u"model.%s.%s.%s(%s)" % (modelName, attributeName,
                                              relationName, repr(value))


if __name__ == '__main__':

    query = ['Form', 'transcription', 'like', 'a']
    query = ['Form', 'transcription', 'like', '%10%']
    query = ['not'] # IndexError
    #query = ['not', ['Form', 'id', '=', 10], ['Form', 'id', '=', 10], ['Form', 'id', '=', 10]] # not(Form.id.=(10))
    query = ['Form', 'dateElicited', '=', '2012-01-01']
    query = ['Form', 'dateElicited', '=', None]
    query = ['Form', 'enterer', '=', 1]
    query = ['Gloss', 'gloss', '=', 'gloss 1']
    queryBuilder = SQLAQueryBuilder('Form', 'debug')
    query = queryBuilder.getSQLAFilter(query)
    print query
