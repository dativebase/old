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
        'corpusfile': ['id', 'filename', 'datetimeModified', 'format', 'restricted'],
        'elicitationmethod': ['id', 'name'],
        'file': ['id', 'name', 'filename', 'MIMEtype', 'size', 'url', 'lossyFilename'],
        'formsearch': ['id', 'name'],
        'translation': ['id', 'transcription', 'grammaticality'],
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

    def getMiniTranslationDict(self, translation):
        return self.getMiniDictFor(translation)

    def getMiniTagDict(self, tag):
        return self.getMiniDictFor(tag)

    def getMiniFileDict(self, file):
        return self.getMiniDictFor(file)

    def getMiniFormSearchDict(self, formSearch):
        return self.getMiniDictFor(formSearch)

    def getMiniOrthographyDict(self, orthography):
        return self.getMiniDictFor(orthography)

    def getMiniCorpusFileDict(self, corpusFile):
        return self.getMiniDictFor(corpusFile)

    def getMiniList(self, listOfModels):
        return [m.getMiniDict() for m in listOfModels]

    def getTranslationsList(self, translations):
        return [self.getMiniTranslationDict(translation) for translation in translations]

    def getTagsList(self, tags):
        return [self.getMiniTagDict(tag) for tag in tags]

    def getFilesList(self, files):
        return [self.getMiniFileDict(file) for file in files]

    def getFormsList(self, forms):
        return [form.getDict() for form in forms]

    def getUsersList(self, users):
        return [self.getMiniUserDict(user) for user in users]

    def getOrthographiesList(self, orthographies):
        return [self.getMiniOrthographyDict(o) for o in orthographies]

    def getCorpusFilesList(self, corpusFiles):
        return [self.getMiniCorpusFileDict(cf) for cf in corpusFiles]

    class Column(object):
        """Empty class that can be used to convert JSON objects into Python
        ones.
        """
        pass
