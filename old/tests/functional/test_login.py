import logging
import simplejson as json
from old.tests import *
from nose.tools import nottest
import old.model as model
from old.model.meta import Session
import old.lib.helpers as h


log = logging.getLogger(__name__)


class TestLoginController(TestController):

    extra_environ_admin = {'test.authentication.role': u'administrator'}
    json_headers = {'Content-Type': 'application/json'}

    # Clear all models in the database except Language and User
    def tearDown(self):
        h.clearAllModels(['Language', 'User'])

    #@nottest
    def test_authenticate(self):
        """Tests that POST /login/authenticate correctly handles authentication attempts."""

        # Invalid username & password
        params = json.dumps({'username': 'x', 'password': 'x'})
        response = self.app.post(url(controller='login', action='authenticate'),
                                params, self.json_headers, status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'The username and password provided are not valid.'

        # Valid username & password
        params = json.dumps({'username': 'admin', 'password': 'admin'})
        response = self.app.post(url(controller='login', action='authenticate'),
                                params, self.json_headers)
        resp = json.loads(response.body)
        assert resp['authenticated'] == True

        # Invalid POST params
        params = json.dumps({'usernamex': 'admin', 'password': 'admin'})
        response = self.app.post(url(controller='login', action='authenticate'),
                                params, self.json_headers, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['username'] == 'Missing value'

    #@nottest
    def test_logout(self):
        """Tests that GET /login/logout logs the user out."""

        # Logout while logged in.
        response = self.app.get(url(controller='login',
                        action='logout'), headers=self.json_headers,
                        extra_environ=self.extra_environ_admin)
        resp = json.loads(response.body)
        assert resp['authenticated'] == False

        # Logout while not logged in.
        response = self.app.get(url(controller='login',
                        action='logout'), headers=self.json_headers, status=401)
        resp = json.loads(response.body)
        assert resp['error'] == u'Authentication is required to access this resource.'

    #@nottest
    def test_email_reset_password(self):
        """Tests that POST /login/email_reset_password sends a user a newly generated password.

        I gave up trying to get Python's smtplib to work on Mac OS X.  The email
        functionality in this controller action appears to work on my Debian
        production system.  See the links below for some Mac head-bashing:

        http://pivotallabs.com/users/chad/blog/articles/507-enabling-the-postfix-mail-daemon-on-leopard
        http://webcache.googleusercontent.com/search?q=cache:http://blog.subtlecoolness.com/2009/06/enabling-postfix-sendmail-on-mac-os-x.html
        http://www.agileapproach.com/blog-entry/how-enable-local-smtp-server-postfix-os-x-leopard.
        """

        # Valid username.
        params = json.dumps({'username': 'contributor'})
        response = self.app.post(url(controller='login',
                    action='email_reset_password'), params, self.json_headers, status=[200, 500])
        resp = json.loads(response.body)
        # smtplib.SMTP('localhost').sendmail may or may not work.  Assert True
        # for a stronger test.
        assert (resp['validUsername'] == True and resp['passwordReset'] == True) or \
            resp['error'] == u'The server is unable to send email.'

        # Invalid username.
        params = json.dumps({'username': 'badusername'})
        response = self.app.post(url(controller='login',
            action='email_reset_password'), params, self.json_headers,
            status=400)
        resp = json.loads(response.body)
        resp['error'] == u'The username provided is not valid.'

        # Invalid POST parameters.
        params = json.dumps({'badparam': 'irrelevant'})
        response = self.app.post(url(controller='login',
            action='email_reset_password'), params, self.json_headers, status=400)
        resp = json.loads(response.body)
        assert resp['errors']['username'] == u'Missing value'
