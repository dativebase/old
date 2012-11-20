"""Pylons environment configuration"""
import os
import re

from mako.lookup import TemplateLookup
from pylons.configuration import PylonsConfig
from pylons.error import handle_mako_error
from sqlalchemy import engine_from_config
from sqlalchemy.interfaces import PoolListener

import old.lib.app_globals as app_globals
import old.lib.helpers
from old.config.routing import make_map
from old.model import init_model

def load_environment(global_conf, app_conf):
    """Configure the Pylons environment via the ``pylons.config``
    object
    """
    config = PylonsConfig()
    
    # Pylons paths
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = dict(root=root,
                 controllers=os.path.join(root, 'controllers'),
                 static_files=os.path.join(root, 'public'),
                 templates=[os.path.join(root, 'templates')])

    #permanent_store=app_conf['permanent_store'],
    #temporary_store=app_conf['temporary_store'],
    #analysis_data=app_conf['analysis_data']

    # Initialize config with the basic options
    config.init_app(global_conf, app_conf, package='old', paths=paths)

    config['routes.map'] = make_map(config)
    config['pylons.app_globals'] = app_globals.Globals(config)
    config['pylons.h'] = old.lib.helpers
    
    # Setup cache object as early as possible
    import pylons
    pylons.cache._push_object(config['pylons.app_globals'].cache)
    

    # Create the Mako TemplateLookup, with the default auto-escaping
    config['pylons.app_globals'].mako_lookup = TemplateLookup(
        directories=paths['templates'],
        error_handler=handle_mako_error,
        module_directory=os.path.join(app_conf['cache_dir'], 'templates'),
        input_encoding='utf-8', default_filters=['escape'],
        imports=['from markupsafe import escape'])

    # Setup the SQLAlchemy database engine
    #engine = engine_from_config(config, 'sqlalchemy.')
    #init_model(engine)

    # CONFIGURATION OPTIONS HERE (note: all config options will override
    # any Pylons config options)

    # Setup the SQLAlchemy database engine
    # *NOTE: Modification.* Check if SQLite is the RDBMS and, if so, give the
    # engine an SQLiteSetup listener which provides the regexp function missing
    # from the SQLite dbapi.  See below for the listener class.
    # Cf. http://groups.google.com/group/pylons-discuss/browse_thread/thread/8c82699e6b6a400c/5c5237c86202e2b8

    RDBMSName = config['sqlalchemy.url'].split(':')[0]
    app_globals.RDBMSName = RDBMSName
    if RDBMSName == 'sqlite':
        engine = engine_from_config(
            config, 'sqlalchemy.', listeners=[SQLiteSetup()])
        # Make LIKE searches case sensitive in SQLite
        engine.execute('PRAGMA case_sensitive_like=ON')
    else:
        engine = engine_from_config(config, 'sqlalchemy.')
    init_model(engine)

    return config


class SQLiteSetup(PoolListener):
    """A PoolListener used to provide the SQLite dbapi with a regexp function.
    """
    def connect(self, conn, conn_record):
        conn.create_function('regexp', 2, self.regexp)

    def regexp(self, expr, item):
        """This is the Python re-based regexp function that we provide for SQLite.
        Note that searches will be case-sensitive by default, which may not be
        the default for the MySQL regexp, depending on the collation."""
        patt = re.compile(expr)
        try:
            return item and patt.search(item) is not None
        # This will make regexp searches work on int, date & datetime fields.
        # I think this is desirable ...
        except TypeError:
            return item and patt.search(str(item)) is not None
