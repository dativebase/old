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
