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
import logging
log = logging.getLogger(__name__)

class Model(object):
    """The Model class holds methods needed (potentially) by all models.  All
    OLD models inherit both from model.model.Model and model.meta.Base (cf.
    model.meta).
    """

    __table_args__ = {
        'mysql_charset': 'utf8',
        'mysql_engine': 'MyISAM'  # Possible values: MyISAM, InnoDB
    }

    # Maps names of tables to the sets of attributes required for mini-dict creation
    table_name2core_attributes = {
        'corpus': ['id', 'name'],
        'corpusfile': ['id', 'filename', 'datetime_modified', 'format', 'restricted'],
        'elicitationmethod': ['id', 'name'],
        'file': ['id', 'name', 'filename', 'MIME_type', 'size', 'url', 'lossy_filename'],
        'formsearch': ['id', 'name'],
        'morphemelanguagemodel': ['id', 'name'],
        'morphology': ['id', 'name'],
        'orthography': ['id', 'name', 'orthography', 'lowercase', 'initial_glottal_stops'],
        'phonology': ['id', 'name'],
        'source': ['id', 'type', 'key', 'journal', 'editor', 'chapter', 'pages',
            'publisher', 'booktitle', 'school', 'institution', 'year', 'author', 'title', 'note'],
        'speaker': ['id', 'first_name', 'last_name', 'dialect'],
        'syntacticcategory': ['id', 'name'],
        'tag': ['id', 'name'],
        'translation': ['id', 'transcription', 'grammaticality'],
        'user': ['id', 'first_name', 'last_name', 'role']
    }

    def get_dict_from_model(self, model, attrs):
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

    def json_loads(self, JSONString):
        try:
            return json.loads(JSONString)
        except (json.decoder.JSONDecodeError, TypeError):
            return None

    def get_mini_dict(self, model=None):
        model = model or self
        return self.get_dict_from_model(model,
                    self.table_name2core_attributes.get(model.__tablename__, []))

    def get_mini_dict_for(self, model):
        return model and self.get_mini_dict(model) or None

    def get_mini_user_dict(self, user):
        return self.get_mini_dict_for(user)

    def get_mini_speaker_dict(self, speaker):
        return self.get_mini_dict_for(speaker)

    def get_mini_elicitation_method_dict(self, elicitation_method):
        return self.get_mini_dict_for(elicitation_method)

    def get_mini_syntactic_category_dict(self, syntactic_category):
        return self.get_mini_dict_for(syntactic_category)

    def get_mini_source_dict(self, source):
        return self.get_mini_dict_for(source)

    def get_mini_translation_dict(self, translation):
        return self.get_mini_dict_for(translation)

    def get_mini_tag_dict(self, tag):
        return self.get_mini_dict_for(tag)

    def get_mini_file_dict(self, file):
        return self.get_mini_dict_for(file)

    def get_mini_form_search_dict(self, form_search):
        return self.get_mini_dict_for(form_search)

    def get_mini_orthography_dict(self, orthography):
        return self.get_mini_dict_for(orthography)

    def get_mini_corpus_file_dict(self, corpus_file):
        return self.get_mini_dict_for(corpus_file)

    def get_mini_list(self, list_of_models):
        return [m.get_mini_dict() for m in list_of_models]

    def get_translations_list(self, translations):
        return [self.get_mini_translation_dict(translation) for translation in translations]

    def get_tags_list(self, tags):
        return [self.get_mini_tag_dict(tag) for tag in tags]

    def get_files_list(self, files):
        return [self.get_mini_file_dict(file) for file in files]

    def get_forms_list(self, forms):
        return [form.get_dict() for form in forms]

    def get_users_list(self, users):
        return [self.get_mini_user_dict(user) for user in users]

    def get_orthographies_list(self, orthographies):
        return [self.get_mini_orthography_dict(o) for o in orthographies]

    def get_corpus_files_list(self, corpus_files):
        return [self.get_mini_corpus_file_dict(cf) for cf in corpus_files]

    class Column(object):
        """Empty class that can be used to convert JSON objects into Python
        ones.
        """
        pass

    def set_attr(self, name, value, changed):
        """Set the value of ``self.name`` to ``value`` only if ``self.name != value``.
        Set ``changed`` to ``True`` if ``self.name`` has changed as a result.  Return
        ``changed``.  Useful in the ``update_<model>`` function of the controllers.

        """

        if getattr(self, name) != value:
            setattr(self, name, value)
            changed = True
        return changed


