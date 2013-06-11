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

import logging
import simplejson as json
from onlinelinguisticdatabase.tests import TestController, url
from nose.tools import nottest
import onlinelinguisticdatabase.model as model
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.lib.helpers as h

log = logging.getLogger(__name__)

class TestLoginController(TestController):
    @nottest
    def test_authenticate(self):
        """Tests that POST /login/authenticate correctly handles authentication attempts."""

        # Invalid username & password
        params = json.dumps({'username': 'x', 'password': 'x'})
        response = self.app.post(url(controller='login', action='authenticate'),
                                params, self.json_headers, status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'The username and password provided are not valid.'
        assert response.content_type == 'application/json'

        # Valid username & password
        params = json.dumps({'username': 'admin', 'password': 'adminA_1'})
        response = self.app.post(url(controller='login', action='authenticate'),
                                params, self.json_headers)
        resp = json.loads(response.body)
        assert resp['authenticated'] == True
        assert response.content_type == 'application/json'

        # Invalid POST params
        params = json.dumps({'usernamex': 'admin', 'password': 'admin'})
        response = self.app.post(url(controller='login', action='authenticate'),
                                params, self.json_headers, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['username'] == 'Missing value'
        assert response.content_type == 'application/json'

    @nottest
    def test_logout(self):
        """Tests that GET /login/logout logs the user out."""

        # Logout while logged in.
        response = self.app.get(url(controller='login',
                        action='logout'), headers=self.json_headers,
                        extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['authenticated'] == False
        assert response.content_type == 'application/json'

        # Logout while not logged in.
        response = self.app.get(url(controller='login',
                        action='logout'), headers=self.json_headers, status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'
        assert response.content_type == 'application/json'

    @nottest
    def test_email_reset_password(self):
        """Tests that POST /login/email_reset_password sends a user a newly generated password.

        I gave up trying to get Python's smtplib to work on Mac OS X.  The email
        functionality in this controller action appears to work on my Debian
        production system.  See the links below for some Mac head-bashing:

        http://pivotallabs.com/users/chad/blog/articles/507-enabling-the-postfix-mail-daemon-on-leopard
        http://webcache.googleusercontent.com/search?q=cache:http://blog.subtlecoolness.com/2009/06/enabling-postfix-sendmail-on-mac-os-x.html
        http://www.agileapproach.com/blog-entry/how-enable-local-smtp-server-postfix-os-x-leopard.
        """

        # Create an application settings so that there is an object language id
        application_settings = h.generate_default_application_settings()
        Session.add(application_settings)
        Session.commit()

        # Get the contributor
        contributor = Session.query(model.User).filter(model.User.username==u'contributor').first()
        contributor_email = contributor.email

        # Ensure that we can authenticate the contributor
        params = json.dumps({'username': 'contributor', 'password': 'contributorC_1'})
        response = self.app.post(url(controller='login', action='authenticate'), params, self.json_headers)
        resp = json.loads(response.body)
        assert resp['authenticated'] == True
        assert response.content_type == 'application/json'

        # Now request a password change.  Depending on whether the mail server is
        # set up correctly and whether we have an internet connection, we will
        # receive a 200 OK or a 500 Server Error:
        config = h.get_config(config_filename='test.ini')
        password_reset_smtp_server = config.get('password_reset_smtp_server')
        test_email_to = config.get('test_email_to')
        to_address = test_email_to or contributor_email
        params = json.dumps({'username': 'contributor'})
        response = self.app.post(url(controller='login', action='email_reset_password'),
                                 params, self.json_headers, status=[200, 500])
        resp = json.loads(response.body)
        assert (response.status_int == 200 and
                resp['valid_username'] == True and
                resp['password_reset'] == True) or (
                response.status_int == 500 and
                resp['error'] == u'The server is unable to send email.')
        assert response.content_type == 'application/json'

        # The email was sent and the password was reset.  Because this is a test,
        # the password was sent back to us in the JSON response.  In a production
        # or development environment, this would not be the case.
        if response.status_int == 200:
            new_password = resp['new_password']
            if password_reset_smtp_server == 'smtp.gmail.com':
                log.info('A new password was emailed via Gmail to %s.' % to_address)
            else:
                log.info('A new password was emailed from localhost to %s.' % to_address)

            # Make sure that the old password no longer works.
            params = json.dumps({'username': 'contributor', 'password': 'contributorC_1'})
            response = self.app.post(url(controller='login', action='authenticate'),
                                     params, self.json_headers, status=401)
            resp = json.loads(response.body)
            assert resp['error'] == u'The username and password provided are not valid.'
            assert response.content_type == 'application/json'

            # Make sure that the new password works.
            params = json.dumps({'username': 'contributor', 'password': new_password})
            response = self.app.post(url(controller='login', action='authenticate'),
                                     params, self.json_headers)
            resp = json.loads(response.body)
            assert resp['authenticated'] == True
            assert response.content_type == 'application/json'

        # If the email was *not* sent and the password was not reset.  Make sure
        # that the old password does still work.
        else:
            log.info('localhost was unable to send email.')
            params = json.dumps({'username': 'contributor', 'password': 'contributorC_1'})
            response = self.app.post(url(controller='login', action='authenticate'), params, self.json_headers)
            resp = json.loads(response.body)
            assert resp['authenticated'] == True
            assert response.content_type == 'application/json'

        # Invalid username.
        params = json.dumps({'username': 'badusername'})
        response = self.app.post(url(controller='login',
            action='email_reset_password'), params, self.json_headers,
            status=400)
        resp = json.loads(response.body)
        resp['error'] == u'The username provided is not valid.'
        assert response.content_type == 'application/json'

        # Invalid POST parameters.
        params = json.dumps({'badparam': 'irrelevant'})
        response = self.app.post(url(controller='login',
            action='email_reset_password'), params, self.json_headers, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['username'] == u'Missing value'
        assert response.content_type == 'application/json'
