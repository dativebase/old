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

"""Contains the :class:`CorsController` and its auxiliary functions.

.. module:: cors
   :synopsis: Contains the controller for responding to CORS preflight OPTIONS
   requests

"""

import logging
from pylons import request, response, session, app_globals, config
from onlinelinguisticdatabase.lib.base import BaseController
import onlinelinguisticdatabase.lib.helpers as h

log = logging.getLogger(__name__)

class CorsController(BaseController):
    """Generate responses to requests on form resources.

    REST Controller styled on the Atom Publishing Protocol.

    """

    @h.restrict('OPTIONS')
    def proceed(self):
        response.status_int = 204
        return

