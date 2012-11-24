"""SQLAlchemy Metadata and Session object"""
import simplejson as json
import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from old.model.model import Model

__all__ = ['Base', 'Session', 'now']

# SQLAlchemy session manager. Updated by model.init_model()
Session = scoped_session(sessionmaker())

# The declarative Base.  It subclasses model.model.Model
Base = declarative_base(cls=Model)

def now():
    return datetime.datetime.utcnow()
