"""Model model"""

import simplejson as json
import datetime
import logging
log = logging.getLogger(__name__)

class Model(object):
    """The Model class holds methods needed (potentially) by all models.  All
    OLD models inherit both from model.model.Model and model.meta.Base (cf.
    model.meta).
    """

    # Maps names of tables to the sets of attributes required for mini-dict creation
    tableName2coreAttributes = {
        'elicitationmethod': ['id', 'name'],
        'file': ['id', 'name', 'filename', 'MIMEtype', 'size', 'url', 'lossyFilename'],
        'gloss': ['id', 'gloss', 'glossGrammaticality'],
        'orthography': ['id', 'name', 'orthography', 'lowercase', 'initialGlottalStops'],
        'source': ['id', 'type', 'key', 'journal', 'editor', 'chapter', 'pages',
            'publisher', 'booktitle', 'school', 'institution', 'year', 'author', 'title', 'note'],
        'speaker': ['id', 'firstName', 'lastName', 'dialect'],
        'syntacticcategory': ['id', 'name'],
        'tag': ['id', 'name'],
        'user': ['id', 'firstName', 'lastName', 'role']
    }

    def getDictFromModel(self, model, attrs):
        """attrs is a list of attribute names (non-relational); returns a dict
        containing all of these attributes and their values.
        """
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

    def getMiniDict(self, model=None):
        model = model or self
        return self.getDictFromModel(model,
                    self.tableName2coreAttributes.get(model.__tablename__, []))

    def getMiniDictFor(self, model):
        return model and self.getMiniDict(model) or None

    def getMiniUserDict(self, user):
        return self.getMiniDictFor(user)

    def getMiniSpeakerDict(self, speaker):
        return self.getMiniDictFor(speaker)

    def getMiniElicitationMethodDict(self, elicitationMethod):
        return self.getMiniDictFor(elicitationMethod)

    def getMiniSyntacticCategoryDict(self, syntacticCategory):
        return self.getMiniDictFor(syntacticCategory)

    def getMiniSourceDict(self, source):
        return self.getMiniDictFor(source)

    def getMiniGlossDict(self, gloss):
        return self.getMiniDictFor(gloss)

    def getMiniTagDict(self, tag):
        return self.getMiniDictFor(tag)

    def getMiniFileDict(self, file):
        return self.getMiniDictFor(file)

    def getMiniOrthographyDict(self, orthography):
        return self.getMiniDictFor(orthography)

    def getMiniList(self, listOfModels):
        return [m.getMiniDict() for m in listOfModels]

    def getGlossesList(self, glosses):
        return [self.getMiniGlossDict(gloss) for gloss in glosses]

    def getTagsList(self, tags):
        return [self.getMiniTagDict(tag) for tag in tags]

    def getFilesList(self, files):
        return [self.getMiniFileDict(file) for file in files]

    def getFormsList(self, forms):
        return [form.getDict() for form in forms]

    def getUsersList(self, users):
        return [self.getMiniUserDict(user) for user in users]

    def getOrthographiesList(self, orthographies):
        return [self.getMiniOrthographyDict(orthography) for orthography in orthographies]

    class Column(object):
        """Empty class that can be used to convert JSON objects into Python
        ones.
        """
        pass
