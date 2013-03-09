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

"""Contains the :class:`ErrorController`.

.. module:: error
   :synopsis: Contains the error controller.

"""

import cgi
from paste.urlparser import PkgResourcesParser
from pylons import request, response
from pylons.controllers.util import forward
from pylons.middleware import error_document_template
from webhelpers.html.builder import literal
import simplejson as json
from onlinelinguisticdatabase.lib.base import BaseController

class ErrorController(BaseController):
    """Generate JSON error objects as required.

    The ``StatusCodeRedirect`` middleware forwards to ``ErrorController`` when
    error-related status codes are returned from the application.

    This behaviour can be altered by changing the parameters to the
    ``StatusCodeRedirect`` middleware in the ``config/middleware.py`` file.

    """

    def document(self):
        """Return a JSON object representing the error.

        Instead of returning an HTML error document (the Pylons default),
        return the JSON object that the controller has specified for the
        response body.  If the response body is not valid JSON, then it has been
        created by Routes; make it into valid JSON.

        """
        resp = request.environ.get('pylons.original_response')
        if resp.status_int == 404:
            try:
                JSONResp = json.loads(resp.body)
            except json.decoder.JSONDecodeError:
                resp.body = json.dumps({'error': u'The resource could not be found.'})
        elif resp.status_int == 500:
            try:
                JSONResp = json.loads(resp.body)
            except json.decoder.JSONDecodeError:
                resp.body = json.dumps({'error': u'Internal Server Error'})
        return resp.body
