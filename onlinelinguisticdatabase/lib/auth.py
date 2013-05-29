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

"""Modules containing functionality used by numerous other modules.

.. module:: lib
   :synopsis: functionality used by numerous other modules.

"""

import simplejson as json
from decorator import decorator
from pylons import session, response
from utils import unauthorized_msg
import logging

log = logging.getLogger(__name__)


def authenticate(target):
    """Authentication decorator.
    
    If user is not logged in and tries to call a controller action with this
    decorator, then the response header status will be ``401 Unauthorized`` and
    the response body will be ``{error: "401 Unauthorized"}``.
    """

    def wrapper(target, *args, **kwargs):
        if getattr(session.get('user'), 'username', None):
            return target(*args, **kwargs)
        response.status_int = 401
        return {'error': 'Authentication is required to access this resource.'}

    return decorator(wrapper)(target)

def authenticate_with_JSON(target):
    """Authentication decorator that returns JSON error messages.
    
    Identical to the authenticate decorator except that the response body is
    json.dumped beforehand.  This is decorator is only needed in those few
    actions whose successful output is not JSON, e.g., the actions that serve
    file data, cf. the ``serve`` and ``serve_file`` actions of the
    ``FilesController`` and ``CorporaController``.
    
    """

    def wrapper(target, *args, **kwargs):
        if getattr(session.get('user'), 'username', None):
            return target(*args, **kwargs)
        response.status_int = 401
        return json.dumps({'error': 'Authentication is required to access this resource.'})

    return decorator(wrapper)(target)

def authorize(roles, users=None, user_id_is_args1=False):
    """Authorization decorator.  If user tries to request a controller action
    but has insufficient authorization, this decorator will respond with a
    header status of '403 Forbidden' and a JSON object explanation.

    The user is unauthorized if *any* of the following are true:

    - the user does not have one of the roles in roles
    - the user is not one of the users in users
    - the user does not have the same id as the id of the entity the action
      takes as argument

    Example 1: (user must be an administrator or a contributor): 
    >@authorize(['administrator', 'contributor'])
    >def action_name(self):
    >   ...

    Example 2: (user must be either an administrator or the contributor with Id 2): 
    >@authorize(['administrator', 'contributor'], [2])
    >def action_name(self):
    >   ...

    Example 3: (user must have the same ID as the entity she is trying to affect): 
    >@authorize(['administrator', 'contributor', 'viewer'], user_id_is_args1=True)
    >def action_name(self, id):
    >   ...

    """

    def wrapper(target, *args, **kwargs):
        # Check for authorization via role.
        role = getattr(session.get('user'), 'role', None)
        if role in roles:
            id = getattr(session.get('user'), 'id', None)
            # Check for authorization via user.
            if users:
                if role != 'administrator' and id not in users:
                    response.status_int = 403
                    return unauthorized_msg
            # Check whether the user id equals the id argument given to the
            # target action.  This is useful, e.g., when a user can only edit
            # their own personal page.
            if user_id_is_args1:
                if role != u'administrator' and int(id) != int(args[1]):
                    response.status_int = 403
                    return unauthorized_msg
            return target(*args, **kwargs)
        else:
            response.status_int = 403
            return unauthorized_msg
    return decorator(wrapper)