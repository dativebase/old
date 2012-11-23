"""The base Controller API

Provides the BaseController class for subclassing.
"""
from pylons.controllers import WSGIController
from pylons.templating import render_mako as render

from old.model.meta import Session
from old.model import User
from pylons import request, response, session, app_globals
import old.lib.helpers as h

class BaseController(WSGIController):

    def __call__(self, environ, start_response):
        """Invoke the Controller"""
        # WSGIController.__call__ dispatches to the Controller method
        # the request is routed to. This routing information is
        # available in environ['pylons.routes_dict']
        environ['past.content_type'] = 'application/json'
        try:
            return WSGIController.__call__(self, environ, start_response)
        finally:
            Session.remove()


    def __before__(self):
        """This method is called before each controller action is called.  It is
        being used here for Pylons functional testing.  Specifically, it is
        being used to control the session and app_globals from within tests.
        
        If present, environ['test.authentication.role'] will evaluate to a user
        role that can be used to retrieve a user with that role from the db and
        put it in the (Beaker) session.  This permits simulation of
        authentication and authorization. See https://groups.google.com/forum/?fromgroups=#!searchin/pylons-discuss/test$20session/pylons-discuss/wiwOQBIxDw8/0yR3z3YiYzYJ
        for the origin of this hack.

        If present, setting environ['test.applicationSettings'] to a truthy
        value will result in app_globals.applicationSettings being set to an
        ApplicationSettings instance.  This permits simulation of the
        application settings cache in app_globals which is used for
        inventory-based validation.  One issue with this approach is that the
        app_globals.applicationSettings attribute is not unset after the test is
        run.  Therefore, the __after__ method (see below) deletes the attribute
        when environ['test.applicationSettings'] is truthy.

        WARNING: overwriting __before__ (or __after__) in a controller class
        (without calling their super methods) will cause nosetests to fail en
        masse.
        """

        if 'test.authentication.role' in request.environ:
            role = unicode(request.environ['test.authentication.role'])
            user = Session.query(User).filter(User.role==role).first()
            if user:
                session['user'] = user
        if 'test.authentication.id' in request.environ:
            user = Session.query(User).get(
                request.environ['test.authentication.id'])
            if user:
                session['user'] = user
        if request.environ.get('test.applicationSettings'):
            app_globals.applicationSettings = h.ApplicationSettings()

    def __after__(self):
        if request.environ.get('test.applicationSettings') and \
        not request.environ.get('test.retainApplicationSettings'):
            del app_globals.applicationSettings
