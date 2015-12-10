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

"""Setup the old application"""
import logging, os
from shutil import copyfile
import pylons.test
from onlinelinguisticdatabase.config.environment import load_environment
from onlinelinguisticdatabase.model.meta import Base, Session
import onlinelinguisticdatabase.lib.helpers as h

log = logging.getLogger(__name__)

def setup_app(command, conf, vars):
    """Commands to setup onlinelinguisticdatabase."""

    config = load_environment(conf.global_conf, conf.local_conf)
    log.info('Environment loaded.')

    Base.metadata.create_all(bind=Session.bind)
    filename = os.path.split(conf.filename)[-1] # e.g., production.ini, development.ini, test.ini, ...

    # Create the ``store`` directory and those for file, analysis and corpora
    # objects and their subdirectories.  See ``lib.utils.py`` for details.
    h.create_OLD_directories(config=config)

    # ISO-639-3 Language data for the languages table
    log.info("Retrieving ISO-639-3 languages data.")
    languages = h.get_language_objects(filename, config)

    # Get default users.
    log.info("Creating a default administrator, contributor and viewer.")
    administrator = h.generate_default_administrator(config_filename=filename)
    contributor = h.generate_default_contributor(config_filename=filename)
    viewer = h.generate_default_viewer(config_filename=filename)

    # If we are running tests, make sure the test db contains only language data.
    if filename == 'test.ini':
        # Permanently drop any existing tables
        Base.metadata.drop_all(bind=Session.bind, checkfirst=True)
        log.info("Existing tables dropped.")

        # Create the tables if they don't already exist
        Base.metadata.create_all(bind=Session.bind, checkfirst=True)
        log.info('Tables created.')

        Session.add_all(languages + [administrator, contributor, viewer])
        Session.commit()

    # Not a test: add a bunch of nice defaults.
    else:
        # Create the _requests_tests.py script
        requests_tests_path = os.path.join(config['pylons.paths']['root'], 'tests',
                                         'scripts', '_requests_tests.py')

        # This line is problematic in production apps because the
        # _requests_tests.py file is not included in the build. So, I'm
        # commenting it out by default.
        # copyfile(requests_tests_path, '_requests_tests.py')

        # Create the tables if they don't already exist
        Base.metadata.create_all(bind=Session.bind, checkfirst=True)
        log.info('Tables created.')

        # Get default home & help pages.
        log.info("Creating default home and help pages.")
        homepage = h.generate_default_home_page()
        helppage = h.generate_default_help_page()
    
        # Get default application settings.
        log.info("Generating default application settings.")
        application_settings = h.generate_default_application_settings()
    
        # Get default tags and categories
        log.info("Creating some useful tags and categories.")
        restricted_tag = h.generate_restricted_tag()
        foreign_word_tag = h.generate_foreign_word_tag()
        S = h.generate_s_syntactic_category()
        N = h.generate_n_syntactic_category()
        V = h.generate_v_syntactic_category()
    
        # Initialize the database
        log.info("Adding defaults.")
        data = [administrator, contributor, viewer, homepage, helppage,
                application_settings, restricted_tag, foreign_word_tag]
        if config['add_language_data'] != '0':
            data += languages
        if config['empty_database'] == '0':
            Session.add_all(data)
            Session.commit()
        log.info("OLD successfully set up.")
