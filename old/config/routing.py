"""Routes configuration

The more specific and detailed routes should be defined first so they
may take precedent over the more generic routes. For more information
refer to the routes manual at http://routes.groovie.org/docs/
"""

from routes import Mapper

def make_map(config):
    """Create, configure and return the routes Mapper"""
    map = Mapper(directory=config['pylons.paths']['controllers'],
                 always_scan=config['debug'])
    map.minimization = False
    map.explicit = False

    # The ErrorController route (handles 404/500 error pages); it should
    # likely stay at the top, ensuring it can always be resolved
    map.connect('/error/{action}', controller='error')
    map.connect('/error/{action}/{id}', controller='error')

    # CUSTOM ROUTES HERE
    map.connect('/forms/update_morpheme_references', controller='forms',
            action='update_morpheme_references', conditions=dict(method='PUT'))

    # SEARCH routes
    map.connect('forms', '/forms', controller='forms',
                action='search', conditions=dict(method='SEARCH'))
    map.connect('files', '/files', controller='files',
                action='search', conditions=dict(method='SEARCH'))
    map.connect('collections', '/collections', controller='oldcollections',
                action='search', conditions=dict(method='SEARCH'))
    map.connect('/collections/search', controller='oldcollections', action='search')
    map.connect('sources', '/sources', controller='sources',
                action='search', conditions=dict(method='SEARCH'))
    map.connect('collectionbackups', '/collectionbackups', controller='collectionbackups',
                action='search', conditions=dict(method='SEARCH'))
    map.connect('formbackups', '/formbackups', controller='formbackups',
                action='search', conditions=dict(method='SEARCH'))
    map.connect('languages', '/languages', controller='languages',
                action='search', conditions=dict(method='SEARCH'))
    map.connect('formsearches', '/formsearches', controller='formsearches',
                action='search', conditions=dict(method='SEARCH'))

    # RESTful resoure mappings
    map.resource('applicationsetting', 'applicationsettings')
    map.resource('collection', 'collections', controller='oldcollections')
    map.resource('collectionbackup', 'collectionbackups')       # read-only
    map.resource('elicitationmethod', 'elicitationmethods')
    map.resource('file', 'files')
    map.resource('form', 'forms')
    map.resource('formsearch', 'formsearches')
    map.resource('formbackup', 'formbackups')       # read-only
    map.resource('gloss', 'glosses')                # read-only
    map.resource('language', 'languages')           # read-only
    map.resource('orthography', 'orthographies')
    map.resource('page', 'pages')
    map.resource('phonology', 'phonologies')
    map.resource('source', 'sources')
    map.resource('speaker', 'speakers')
    map.resource('syntacticcategory', 'syntacticcategories')
    map.resource('tag', 'tags')
    map.resource('user', 'users')

    # Map '/collections' to oldcollections controller (conflict with Python
    # collections module).
    map.connect('collections', controller='oldcollections')

    # Pylons Defaults
    map.connect('/{controller}/{action}')
    map.connect('/{controller}/{id}/{action}')

    return map