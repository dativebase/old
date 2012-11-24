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
