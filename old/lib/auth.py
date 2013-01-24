import simplejson as json
from decorator import decorator
from pylons import session, response
from utils import unauthorizedMsg
import logging

log = logging.getLogger(__name__)


def authenticate(target):
    """Authentication decorator.  If user is not logged in and tries to call
    a controller action with this decorator, then the response header status
    will be '401 Unauthorized' and the response body will be
    {error: '401 Unauthorized'}.
    """

    def wrapper(target, *args, **kwargs):
        if getattr(session.get('user'), 'username', None):
            return target(*args, **kwargs)
        response.status_int = 401
        return {'error': 'Authentication is required to access this resource.'}

    return decorator(wrapper)(target)

def authenticateWithJSON(target):
    """Identical to the authenticate decorator except that the response body is
    json.dumped beforehand.  This is decorator is only needed in the retrieve
    action of controllers/files.py
    """

    def wrapper(target, *args, **kwargs):
        if getattr(session.get('user'), 'username', None):
            return target(*args, **kwargs)
        response.status_int = 401
        return json.dumps({'error': 'Authentication is required to access this resource.'})

    return decorator(wrapper)(target)

def authorize(roles, users=None, userIDIsArgs1=False):
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
    >def actionName(self):
    >   ...

    Example 2: (user must be either an administrator or the contributor with Id 2): 
    >@authorize(['administrator', 'contributor'], [2])
    >def actionName(self):
    >   ...

    Example 3: (user must have the same ID as the entity she is trying to affect): 
    >@authorize(['administrator', 'contributor', 'viewer'], userIDIsArgs1=True)
    >def actionName(self, id):
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
                    return unauthorizedMsg
            # Check whether the user id equals the id argument given to the
            # target action.  This is useful, e.g., when a user can only edit
            # their own personal page.
            if userIDIsArgs1:
                if role != u'administrator' and int(id) != int(args[1]):
                    response.status_int = 403
                    return unauthorizedMsg
            return target(*args, **kwargs)
        else:
            response.status_int = 403
            return unauthorizedMsg
    return decorator(wrapper)