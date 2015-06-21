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

"""Pylons middleware initialization.

.. module:: middleware
   :synopsis: middleware initialization.

"""
from beaker.middleware import SessionMiddleware
from paste.cascade import Cascade
from paste.registry import RegistryManager
from paste.urlparser import StaticURLParser
from paste.deploy.converters import asbool
from pylons.middleware import ErrorHandler, StatusCodeRedirect
from pylons.wsgiapp import PylonsApp
from routes.middleware import RoutesMiddleware
from onlinelinguisticdatabase.config.environment import load_environment
import logging
import pprint

log = logging.getLogger(__name__)

class HTML2JSONContentType(object):
    """Middleware transforms ``Content-Type: text/html`` headers to ``Content-Type: application/json``.

    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, exc_info=None):

            new_headers = dict(headers)

            if dict(headers).get('Content-Type') == 'text/html; charset=utf-8':
                new_headers['Content-Type'] = 'application/json'

            # CORS stuff. See http://stackoverflow.com/questions/2771974/modify-headers-in-pylons-using-middleware

            try:
                origin = environ.get('HTTP_ORIGIN')
            except Exception, e:
                origin = 'http://dativebeta.lingsync.org'
            # new_headers['Access-Control-Allow-Origin'] = 'http://localhost:9000'
            new_headers['Access-Control-Allow-Origin'] = origin

            # Use this header to indicate that cookies should be included in CORS requests.
            new_headers['Access-Control-Allow-Credentials'] = 'true'

            # What was here before: new_headers['Access-Control-Allow-Methods'] = 'OPTIONS, GET, POST'
            new_headers['Access-Control-Allow-Methods'] = 'GET, HEAD, POST, PUT, DELETE, TRACE, CONNECT, COPY, OPTIONS, SEARCH'

            # What was here before: new_headers['Access-Control-Allow-Headers'] = 'Content-Type, content-type, Depth, User-Agent, X-File-Size, X-Requested-With, If-Modified-Since, X-File-Name, Cache-Control'
            new_headers['Access-Control-Allow-Headers'] = 'Content-Type, content-type'

            # This causes the preflight result to be cached for specified milliseconds.
            # From LingSync's CouchDB config
            # NOTE: Comment out during development
            #new_headers['Access-Control-Max-Age'] = '12345'

            # Access-Control-Expose-Headers (optional)
            # The XMLHttpRequest 2 object has a getResponseHeader() method that returns the
            # value of a particular response header. During a CORS request, the
            # getResponseHeader() method can only access simple response headers. Simple
            # response headers are defined as follows:
            #
            #    Cache-Control
            #    Content-Language
            #    Content-Type
            #    Expires
            #    Last-Modified
            #    Pragma
            #
            # If you want clients to be able to access other headers, you have to use
            # the Access-Control-Expose-Headers header. The value of this header is a
            # comma-delimited list of response headers you want to expose to the client.
            # NOTE: Commented this out for debuggin ...
            new_headers['Access-Control-Expose-Headers'] = 'Access-Control-Allow-Origin, Access-Control-Allow-Credentials'

            headers = new_headers.items()

            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)


def make_app(global_conf, full_stack=False, static_files=True, **app_conf):
    """Create a Pylons WSGI application and return it

    ``global_conf``
        The inherited configuration for this application. Normally from
        the [DEFAULT] section of the Paste ini file.

    ``full_stack``
        Whether this application provides a full WSGI stack (by default,
        meaning it handles its own exceptions and errors). Disable
        full_stack when this application is "managed" by another WSGI
        middleware.

    ``static_files``
        Whether this application serves its own static files; disable
        when another web server is responsible for serving them.

    ``app_conf``
        The application's local configuration. Normally specified in
        the [app:<name>] section of the Paste ini file (where <name>
        defaults to main).

    """
    # Configure the Pylons environment
    config = load_environment(global_conf, app_conf)

    # The Pylons WSGI app
    app = PylonsApp(config=config)

    # Routing/Session Middleware
    app = RoutesMiddleware(app, config['routes.map'], singleton=False)
    app = SessionMiddleware(app, config)

    # At some point it seems that Pylons converts the Content-Type of any
    # response without a 200 OK status to 'text/html; charset=utf-8'.  Well
    # no more Pylons!  The HTML2JSONContentType middleware zaps those
    # nasty text/html content types and converts them to application/json!
    app = HTML2JSONContentType(app)

    if asbool(full_stack):
        # Handle Python exceptions
        app = ErrorHandler(app, global_conf, **config['pylons.errorware'])

        # Display error documents for 401, 403, 404 status codes (and
        # 500 when debug is disabled)
        if asbool(config['debug']):
            app = StatusCodeRedirect(app)
        else:
            app = StatusCodeRedirect(app, [400, 401, 403, 404, 500])

    # Establish the Registry for this application
    app = RegistryManager(app)

    if asbool(static_files):
        # Serve static files
        static_app = StaticURLParser(config['pylons.paths']['static_files'])
        app = Cascade([static_app, app])
    app.config = config
    return app

