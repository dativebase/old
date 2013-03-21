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

from onlinelinguisticdatabase.model.meta import Session, Base

from onlinelinguisticdatabase.model.applicationsettings import ApplicationSettings
from onlinelinguisticdatabase.model.collection import Collection
from onlinelinguisticdatabase.model.collectionbackup import CollectionBackup
from onlinelinguisticdatabase.model.corpus import Corpus, CorpusFile
from onlinelinguisticdatabase.model.corpusbackup import CorpusBackup
from onlinelinguisticdatabase.model.elicitationmethod import ElicitationMethod
from onlinelinguisticdatabase.model.file import File
from onlinelinguisticdatabase.model.form import Form, FormFile
from onlinelinguisticdatabase.model.formbackup import FormBackup
from onlinelinguisticdatabase.model.formsearch import FormSearch
from onlinelinguisticdatabase.model.translation import Translation
from onlinelinguisticdatabase.model.language import Language
from onlinelinguisticdatabase.model.orthography import Orthography
from onlinelinguisticdatabase.model.page import Page
from onlinelinguisticdatabase.model.phonology import Phonology
from onlinelinguisticdatabase.model.phonologybackup import PhonologyBackup
from onlinelinguisticdatabase.model.source import Source
from onlinelinguisticdatabase.model.speaker import Speaker
from onlinelinguisticdatabase.model.syntacticcategory import SyntacticCategory
from onlinelinguisticdatabase.model.tag import Tag
from onlinelinguisticdatabase.model.user import User, UserForm

def init_model(engine):
    """Call me before using any of the tables or classes in the model"""
    #Session.configure(autoflush=True, bind=engine)
    Session.configure(bind=engine)
