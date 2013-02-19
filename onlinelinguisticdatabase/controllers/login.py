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

import os
import logging
import socket
import simplejson as json
from paste.deploy import appconfig
from pylons import url, request, response, session, app_globals, config
from pylons.decorators.rest import restrict
from pylons.decorators import validate
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import LoginSchema, PasswordResetSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model import Form, User
from onlinelinguisticdatabase.model.meta import Session

log = logging.getLogger(__name__)

class LoginController(BaseController):

    here = appconfig('config:test.ini', relative_to='.')['here']

    @h.jsonify
    @h.restrict('POST')
    def authenticate(self):
        """POST /login/authenticate: request body should be a JSON object of the
        form {username: '...', password: '...'}.  Response is a JSON object with
        a boolean 'authenticated' property and (optionally) an 'errors' object
        property.
        """
        try:
            schema = LoginSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
            username = result['username']
            userFromUsername = Session.query(User).filter(User.username==username).first()
            if userFromUsername:
                salt = userFromUsername.salt
                password = unicode(h.encryptPassword(result['password'], str(salt)))
                user = Session.query(User).filter(User.username==username).filter(
                    User.password==password).first()
                if user:
                    session['user'] = user
                    session.save()
                    return {'authenticated': True}
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
        """Logout user by deleting the session."""
        session.delete()
        return {'authenticated': False}

    @h.jsonify
    @h.restrict('POST')
    def email_reset_password(self):
        """Try to reset the user's password and email them a new one.
        Response is a JSON object with two boolean properties:

            {'validUsername': True/False, 'passwordReset': False/False}
        """
        try:
            schema = PasswordResetSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
            user = Session.query(User).filter(User.username==result['username']).first()
            if user:
                try:
                    newPassword = h.generatePassword()
                    h.sendPasswordResetEmailTo(user, newPassword, config=config)
                    user.password = unicode(h.encryptPassword(newPassword, str(user.salt)))
                    Session.add(user)
                    Session.commit()
                    if os.path.split(config['__file__'])[-1] == 'test.ini':
                        return {'validUsername': True, 'passwordReset': True,
                                'newPassword': newPassword}
                    else:
                        return {'validUsername': True, 'passwordReset': True}
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