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
    map.connect('forms', '/forms', controller='forms',
                action='search', conditions=dict(method='SEARCH'))

    # RESTful resoure mappings
    map.resource('orthography', 'orthographies')
    map.resource('applicationsetting', 'applicationsettings')
    map.resource('collection', 'oldcollections')
    map.resource('collectionbackup', 'collectionbackups')
    map.resource('collectionfile', 'collectionfiles')
    map.resource('collectionform', 'collectionforms')
    map.resource('elicitationmethod', 'elicitationmethods')
    map.resource('file', 'files')
    map.resource('form', 'forms')
    map.resource('formsearch', 'formsearches')
    map.resource('formbackup', 'formbackups')
    map.resource('formfile', 'formfiles')
    map.resource('formkeyword', 'formkeywords')
    map.resource('gloss', 'glosses')
    map.resource('keyword', 'keywords')
    map.resource('language', 'languages')
    map.resource('page', 'pages')
    map.resource('phonology', 'phonologies')
    map.resource('source', 'sources')
    map.resource('speaker', 'speakers')
    map.resource('syntacticcategory', 'syntacticcategories')
    map.resource('user', 'users')
    map.resource('userform', 'userforms')

    # Map '/collections' to oldcollections controller (conflict with Python
    # collections module).
    map.connect('collections', controller='oldcollections')

    # Pylons Defaults
    map.connect('/{controller}/{action}')
    map.connect('/{controller}/{id}/{action}')

    return map