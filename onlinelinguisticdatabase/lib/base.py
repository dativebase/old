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

"""The base Controller API

Provides the BaseController class for subclassing.
"""
from pylons.controllers import WSGIController
from pylons.templating import render_mako as render

from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import User
from pylons import request, response, session, app_globals
import onlinelinguisticdatabase.lib.helpers as h

import logging
log = logging.getLogger(__name__)

class BaseController(WSGIController):

    def __call__(self, environ, start_response):
        """Invoke the Controller"""
        # WSGIController.__call__ dispatches to the Controller method
        # the request is routed to. This routing information is
        # available in environ['pylons.routes_dict']
        # environ['paste.content_type'] = 'application/json'
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

        If present, setting environ['test.application_settings'] to a truthy
        value will result in app_globals.application_settings being set to an
        ApplicationSettings instance.  This permits simulation of the
        application settings cache in app_globals which is used for
        inventory-based validation.  One issue with this approach is that the
        app_globals.application_settings attribute is not unset after the test is
        run.  Therefore, the __after__ method (see below) deletes the attribute
        when environ['test.application_settings'] is truthy.

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
        if request.environ.get('test.application_settings'):
            app_globals.application_settings = h.ApplicationSettings()

    def __after__(self):
        if request.environ.get('test.application_settings') and \
        not request.environ.get('test.retain_application_settings'):
            del app_globals.application_settings
