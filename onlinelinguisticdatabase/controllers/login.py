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

"""Contains the :class:`LoginController`.

.. module:: login
   :synopsis: Contains the login controller.

"""

import os
import logging
import simplejson as json
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import LoginSchema, PasswordResetSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import User
from onlinelinguisticdatabase.model.meta import Session

log = logging.getLogger(__name__)

class LoginController(BaseController):
    """Handles authentication-related functionality.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    here = h.get_config(config=config).get('here')

    @h.jsonify
    @h.restrict('POST', 'OPTIONS')
    def authenticate(self):
        """Session-based authentication.

        :URL: ``POST /login/authenticate``
        :request body: A JSON object with ``"username"`` and ``"password"``
            string values
        :returns: ``{"authenticated": True}`` on success, an error dictionary on
            failure.

        """
        try:
            schema = LoginSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
            username = result['username']
            user_from_username = Session.query(User).filter(User.username==username).first()
            if user_from_username:
                salt = user_from_username.salt
                password = unicode(h.encrypt_password(result['password'], str(salt)))
                user = Session.query(User).filter(User.username==username).filter(
                    User.password==password).first()
                if user:
                    session['user'] = user
                    session.save()
                    return {'authenticated': True, 'user': user}
                else:
                    response.status_int = 401
                    return {'error': u'The username and password provided are not valid.'}
            else:
                response.status_int = 401
                return {'error': u'The username and password provided are not valid.'}
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def logout(self):
        """Logout user by deleting the session.

        :URL: ``POST /login/logout``.
        :returns: ``{"authenticated": False}``.

        """
        session.delete()
        return {'authenticated': False}

    @h.jsonify
    @h.restrict('POST')
    def email_reset_password(self):
        """Reset the user's password and email them a new one.

        :URL: ``POST /login/email_reset_password``
        :request body: a JSON object with a ``"username"`` attribute.
        :returns: a dictionary with ``'valid_username'`` and ``'password_reset'``
            keys whose values are booleans.

        """
        try:
            schema = PasswordResetSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
            user = Session.query(User).filter(User.username==result['username']).first()
            if user:
                try:
                    new_password = h.generate_password()
                    h.send_password_reset_email_to(user, new_password, config=config)
                    user.password = unicode(h.encrypt_password(new_password, str(user.salt)))
                    Session.add(user)
                    Session.commit()
                    if os.path.split(config['__file__'])[-1] == 'test.ini':
                        return {'valid_username': True, 'password_reset': True,
                                'new_password': new_password}
                    else:
                        return {'valid_username': True, 'password_reset': True}
                except:     # socket.error was too specific ...
                    response.status_int = 500
                    return {'error': 'The server is unable to send email.'}
            else:
                response.status_int = 400
                return {'error': 'The username provided is not valid.'}
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}
