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
import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from onlinelinguisticdatabase.model.model import Model

__all__ = ['Base', 'Session', 'now']

# SQLAlchemy session manager. Updated by model.init_model()
# Mar 18, 2014: I added expire_on_commit=False because I was getting 
# DetachedInstanceError: Parent instance <File at 0x105399690> is not bound to a Session; lazy load operation of attribute 'speaker' cannot proceed
# when trying to call get_dict() after returning a freshly deleted File object.
# Cf. http://stackoverflow.com/questions/3039567/sqlalchemy-detachedinstanceerror-with-regular-attribute-not-a-relation?rq=1
# WARNING: expire_on_commit=False was causing issues with datetime objects variably having microsecond values ...
#Session = scoped_session(sessionmaker(expire_on_commit=False))
Session = scoped_session(sessionmaker())

# The declarative Base.  It subclasses model.model.Model
Base = declarative_base(cls=Model)

def now():
    return datetime.datetime.utcnow()
