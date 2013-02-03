import cgi

from paste.urlparser import PkgResourcesParser
from pylons import request, response
from pylons.controllers.util import forward
from pylons.middleware import error_document_template
from webhelpers.html.builder import literal

import simplejson as json

from old.lib.base import BaseController

class ErrorController(BaseController):

    """Generates error documents as and when they are required.

    The ErrorDocuments middleware forwards to ErrorController when error
    related status codes are returned from the application.

    This behaviour can be altered by changing the parameters to the
    ErrorDocuments middleware in your config/middleware.py file.

    """

    def document(self):
        """Instead of returning an HTML error document (the Pylons default),
        return the JSON object that the controller has specified for the
        response body.  If the response body is not valid JSON, then it has been
        created by Routes and we need to make it into valid JSON (just to be
        consistent).  A bit hacky...
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
