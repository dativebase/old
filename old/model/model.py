"""Model model"""

import simplejson as json
import datetime

class Model(object):
    """The Model class holds methods needed (potentially) by all models.  All
    OLD models inherit both from model.model.Model and model.meta.Base (cf.
    model.meta).
    """

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
        return self.getDictFromModel(user, ['id', 'firstName', 'lastName', 'role'])

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

    def getMiniOrthographyDict(self, orthography):
        return self.getDictFromModel(orthography,
            ['id', 'name', 'orthography', 'lowercase', 'initialGlottalStops'])

    def getGlossesList(self, glosses):
        return [self.getMiniGlossDict(gloss) for gloss in glosses]

    def getTagsList(self, tags):
        return [self.getMiniTagDict(tag) for tag in tags]

    def getFilesList(self, files):
        return [self.getMiniFileDict(file) for file in files]

    def getUsersList(self, users):
        return [self.getMiniUserDict(user) for user in users]

    def getOrthographiesList(self, orthographies):
        return [self.getMiniOrthographyDict(orthography) for orthography in orthographies]

    class Column(object):
        """Empty class that can be used to convert JSON objects into Python
        ones.
        """
        pass
