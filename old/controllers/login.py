import logging
import smtplib
import socket
import simplejson as json

from pylons import url, request, response, session, app_globals, tmpl_context as c
from pylons.decorators.rest import restrict
from pylons.decorators import validate

from formencode.validators import Invalid

from old.lib.base import BaseController
from old.lib.schemata import LoginSchema, PasswordResetSchema
import old.lib.helpers as h

from old.model import Form, User
from old.model.meta import Session

log = logging.getLogger(__name__)

class LoginController(BaseController):

    @restrict('POST')
    def authenticate(self):
        """POST /login/authenticate: request body should be a JSON object of the
        form {username: '...', password: '...'}.  Response is a JSON object with
        a boolean 'authenticated' property and (optionally) an 'errors' object
        property.

        """

        response.content_type = 'application/json'

        try:
            schema = LoginSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
        except h.JSONDecodeError:
            response.status_int = 400
            result = h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            result = json.dumps({'errors': e.unpack_errors()})
        else:
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
                    result = json.dumps({'authenticated': True})
                else:
                    response.status_int = 401
                    result = json.dumps(
                        {'error': u'The username and password provided are not valid.'})
            else:
                response.status_int = 401
                result = json.dumps(
                    {'error': u'The username and password provided are not valid.'})

        return result

    @restrict('GET')
    @h.authenticate
    def logout(self):
        """Logout user by deleting the session."""

        response.content_type = 'application/json'
        session.delete()
        return json.dumps({'authenticated': False})

    @restrict('POST')
    def email_reset_password(self):
        """Try to reset the user's password and email them a new one.
        Response is a JSON object with two boolean properties:

            {'validUsername': True/False, 'passwordReset': False/False}
        """

        response.content_type = 'application/json'
        try:
            schema = PasswordResetSchema()
            values = json.loads(unicode(request.body, request.charset))
            result = schema.to_python(values)
        except h.JSONDecodeError:
            response.status_int = 400
            result = h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            result = json.dumps({'errors': e.unpack_errors()})
        else:
            user = Session.query(User).filter(
                User.username==result['username']).first()
            if user:
                # Generate a new password.
                newPassword = h.generatePassword()
                # Sender email: e.g., bla@old.org, else old@old.org.
                try:
                    lang = h.getApplicationSettings().objectLanguageId
                except AttributeError:
                    lang = ''
                lang = lang if lang else 'old'
                sender = '%s@old.org' % lang
                # Receiver email.
                receivers = [user.email]
                # Compose the message.
                appName = lang.upper() + ' OLD' if lang != 'old' else 'OLD'
                appURL = url('/', qualified=True)
                message = 'From: %s <%s>\n' % (appName, sender)
                message += 'To: %s %s <%s>\n' % (user.firstName, user.lastName,
                                                 user.email)
                message += 'Subject: %s Password Reset\n\n\n' % appName
                message += 'Your password at %s has been reset to %s.\n\n' % (
                    appURL, newPassword)
                message += 'Please change it once you have logged in.\n\n'
                message += '(Do not reply to this email.)'

                try:
                    smtpObj = smtplib.SMTP('localhost')
                    smtpObj.sendmail(sender, receivers, message)
                    smtpObj.quit()
                    user.password = newPassword
                    Session.commit()
                    result = json.dumps({'validUsername': True, 'passwordReset': True})
                except socket.error:
                    response.status_int = 500
                    result = json.dumps({'error': 'The server is unable to send email.'})
            else:
                response.status_int = 400
                result = json.dumps({'error': 'The username provided is not valid.'})

        return result