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

"""Routes configuration.

.. module:: routing
   :synopsis: Routes configuration.

The more specific and detailed routes should be defined first so they
may take precedent over the more generic routes. For more information
refer to the routes manual at http://routes.groovie.org/docs/
"""

from routes import Mapper

def search_connect(map, name, controller=None):
    """Create a SEARCH mapping for the input ``name``/``controller``.
    
    E.g., ``map = search_connect(map, 'forms')`` causes ``SEARCH /forms`` to
    route to :func:`FormsController.search`, etc.

    """
    controller = controller or name
    map.connect(name, '/%s' % name, controller=controller,
                action='search', conditions=dict(method='SEARCH'))
    map.connect('/%s/search' % name, controller=controller,
                action='search', conditions=dict(method='POST'))
    map.connect('/%s/new_search' % name, controller=controller,
                action='new_search', conditions=dict(method='GET'))
    return map

def make_map(config):
    """Create, configure and return the routes Mapper.

    Define the RESTful interface, the SEARCH interface on select resources and
    the non-RESTful interfaces, e.g., ``GET /forms/history/id``.

    """
    map = Mapper(directory=config['pylons.paths']['controllers'],
                 always_scan=config['debug'])
    map.minimization = False
    map.explicit = False

    # The ErrorController route (handles 404/500 error pages); it should
    # likely stay at the top, ensuring it can always be resolved
    map.connect('/error/{action}', controller='error')
    map.connect('/error/{id}/{action}', controller='error')

    # CORS preflight OPTIONS requests---don't interfere with them
    map.connect('/*garbage',
        conditions=dict(method='OPTIONS'), controller='cors', action='proceed')

    # CUSTOM ROUTES HERE
    map.connect('/collections/{id}/history', controller='oldcollections', action='history')

    # Note: this is the unconventional "search connect" mapping for corpora
    # resources. To search across corpora, you need to issue a SEARCH/POST
    # /corpora/searchcorpora request.
    map.connect('/corpora/searchcorpora', controller='corpora',
                action='search_corpora',
                conditions=dict(method=['POST', 'SEARCH']))
    map.connect('/corpora/new_search_corpora', controller='corpora',
                action='new_search_corpora', conditions=dict(method='GET'))

    map.connect('/corpora/{id}/get_word_category_sequences', controller='corpora', action='get_word_category_sequences',
                conditions=dict(method='GET'))
    map.connect('/corpora/{id}', controller='corpora', action='search',
                conditions=dict(method='SEARCH'))
    map.connect('/corpora/{id}/history', controller='corpora', action='history')
    map.connect('/corpora/{id}/search', controller='corpora', action='search',
                conditions=dict(method='POST'))
    map.connect('/corpora/{id}/servefile/{file_id}', controller='corpora',
                action='servefile', conditions=dict(method='GET'))
    map.connect('/corpora/{id}/tgrep2', controller='corpora',
                action='tgrep2', conditions=dict(method=['POST', 'SEARCH']))
    map.connect('/corpora/{id}/writetofile', controller='corpora',
                action='writetofile', conditions=dict(method='PUT'))
    map.connect('/corpora/new_search', controller='corpora', action='new_search')

    map.connect('/files/{id}/serve', controller='files', action='serve')
    map.connect('/files/{id}/serve_reduced', controller='files', action='serve_reduced')

    map.connect('/forms/{id}/history', controller='forms', action='history')
    map.connect('/forms/remember', controller='forms', action='remember')
    map.connect('/forms/update_morpheme_references', controller='forms',
                action='update_morpheme_references', conditions=dict(method='PUT'))

    map.connect('/login/authenticate', controller='login', action='authenticate')
    map.connect('/login/logout', controller='login', action='logout')
    map.connect('/login/email_reset_password', controller='login', action='email_reset_password')

    map.connect('/morphemelanguagemodels/{id}/compute_perplexity', controller='morphemelanguagemodels',
                action='compute_perplexity', conditions=dict(method='PUT'))
    map.connect('/morphemelanguagemodels/{id}/generate', controller='morphemelanguagemodels',
                action='generate', conditions=dict(method='PUT'))
    map.connect('/morphemelanguagemodels/{id}/history', controller='morphemelanguagemodels', action='history')
    map.connect('/morphemelanguagemodels/{id}/get_probabilities', controller='morphemelanguagemodels',
                action='get_probabilities', conditions=dict(method='PUT'))
    map.connect('/morphemelanguagemodels/{id}/serve_arpa', controller='morphemelanguagemodels',
                action='serve_arpa', conditions=dict(method='GET'))

    map.connect('/morphologicalparsers/{id}/applydown', controller='morphologicalparsers',
                action='applydown', conditions=dict(method='PUT'))
    map.connect('/morphologicalparsers/{id}/applyup', controller='morphologicalparsers',
                action='applyup', conditions=dict(method='PUT'))
    map.connect('/morphologicalparsers/{id}/export', controller='morphologicalparsers',
                action='export', conditions=dict(method='GET'))
    map.connect('/morphologicalparsers/{id}/generate', controller='morphologicalparsers',
                action='generate', conditions=dict(method='PUT'))
    map.connect('/morphologicalparsers/{id}/generate_and_compile', controller='morphologicalparsers',
                action='generate_and_compile', conditions=dict(method='PUT'))
    map.connect('/morphologicalparsers/{id}/history', controller='morphologicalparsers', action='history')
    map.connect('/morphologicalparsers/{id}/parse', controller='morphologicalparsers', action='parse', 
                conditions=dict(method='PUT'))
    map.connect('/morphologicalparsers/{id}/servecompiled', controller='morphologicalparsers',
                action='servecompiled', conditions=dict(method='GET'))

    map.connect('/morphologies/{id}/applydown', controller='morphologies',
                action='applydown', conditions=dict(method='PUT'))
    map.connect('/morphologies/{id}/applyup', controller='morphologies',
                action='applyup', conditions=dict(method='PUT'))
    map.connect('/morphologies/{id}/generate', controller='morphologies',
                action='generate', conditions=dict(method='PUT'))
    map.connect('/morphologies/{id}/generate_and_compile', controller='morphologies',
                action='generate_and_compile', conditions=dict(method='PUT'))
    map.connect('/morphologies/{id}/history', controller='morphologies', action='history')
    map.connect('/morphologies/{id}/servecompiled', controller='morphologies',
                action='servecompiled', conditions=dict(method='GET'))

    map.connect('/phonologies/{id}/applydown', controller='phonologies',
                action='applydown', conditions=dict(method='PUT'))
    map.connect('/phonologies/{id}/compile', controller='phonologies',
                action='compile', conditions=dict(method='PUT'))
    map.connect('/phonologies/{id}/history', controller='phonologies', action='history')
    map.connect('/phonologies/{id}/phonologize', controller='phonologies',
                action='applydown', conditions=dict(method='PUT'))
    map.connect('/phonologies/{id}/runtests', controller='phonologies',
                action='runtests', conditions=dict(method='GET'))
    map.connect('/phonologies/{id}/servecompiled', controller='phonologies',
                action='servecompiled', conditions=dict(method='GET'))

    # SEARCH routes
    map = search_connect(map, 'collectionbackups')
    map = search_connect(map, 'collections', 'oldcollections')
    map = search_connect(map, 'corpusbackups')
    map = search_connect(map, 'files')
    map = search_connect(map, 'formbackups')
    map = search_connect(map, 'forms')
    map = search_connect(map, 'formsearches')
    map = search_connect(map, 'languages')
    map = search_connect(map, 'sources')
    map = search_connect(map, 'morphologies')
    map = search_connect(map, 'phonologies')
    map = search_connect(map, 'morphemelanguagemodels')
    map = search_connect(map, 'morphologicalparsers')

    # rememberedforms "resource"
    map.connect("rememberedforms", "/rememberedforms/{id}",
        controller="rememberedforms", action="show",
        conditions=dict(method=["GET"]))
    map.connect("/rememberedforms/{id}",
        controller="rememberedforms", action="update",
        conditions=dict(method=["PUT"]))
    map.connect("rememberedforms", "/rememberedforms/{id}",
        controller='rememberedforms', action='search',
        conditions=dict(method='SEARCH'))
    map.connect("/rememberedforms/{id}/search",
        controller='rememberedforms', action='search',
        conditions=dict(method='POST'))

    # RESTful resoure mappings
    map.resource('applicationsetting', 'applicationsettings')
    map.resource('collection', 'collections', controller='oldcollections')
    map.resource('collectionbackup', 'collectionbackups')       # read-only
    map.resource('corpus', 'corpora')
    map.resource('corpusbackup', 'corpusbackups')   # read-only
    map.resource('elicitationmethod', 'elicitationmethods')
    map.resource('file', 'files')
    map.resource('form', 'forms')
    map.resource('formsearch', 'formsearches')
    map.resource('formbackup', 'formbackups')       # read-only
    map.resource('language', 'languages')           # read-only
    map.resource('morphemelanguagemodel', 'morphemelanguagemodels')
    map.resource('morphemelanguagemodelbackup', 'morphemelanguagemodelbackups')       # read-only
    map.resource('morphologicalparser', 'morphologicalparsers')
    map.resource('morphologicalparserbackup', 'morphologicalparserbackups')       # read-only
    map.resource('morphology', 'morphologies')
    map.resource('morphologybackup', 'morphologybackups')       # read-only
    map.resource('orthography', 'orthographies')
    map.resource('page', 'pages')
    map.resource('phonology', 'phonologies')
    map.resource('phonologybackup', 'phonologybackups')       # read-only
    map.resource('source', 'sources')
    map.resource('speaker', 'speakers')
    map.resource('syntacticcategory', 'syntacticcategories')
    map.resource('tag', 'tags')
    map.resource('user', 'users')

    # Map '/collections' to oldcollections controller (conflict with Python
    # collections module).
    map.connect('collections', controller='oldcollections')

    # Pylons Defaults
    #map.connect('/{controller}/{action}')
    #map.connect('/{controller}/{id}/{action}')

    return map
