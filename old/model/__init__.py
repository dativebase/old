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

"""The application's model objects"""

from old.model.meta import Session, Base

from old.model.applicationsettings import ApplicationSettings
from old.model.collection import Collection
from old.model.collectionbackup import CollectionBackup
from old.model.elicitationmethod import ElicitationMethod
from old.model.file import File
from old.model.form import Form, FormFile
from old.model.formbackup import FormBackup
from old.model.formsearch import FormSearch
from old.model.gloss import Gloss
from old.model.language import Language
from old.model.orthography import Orthography
from old.model.page import Page
from old.model.phonology import Phonology
from old.model.source import Source
from old.model.speaker import Speaker
from old.model.syntacticcategory import SyntacticCategory
from old.model.tag import Tag
from old.model.user import User, UserForm

def init_model(engine):
    """Call me before using any of the tables or classes in the model"""
    Session.configure(bind=engine)
