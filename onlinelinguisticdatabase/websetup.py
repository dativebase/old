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
import logging, os, datetime
from shutil import copyfile
import pylons.test
from onlinelinguisticdatabase.config.environment import load_environment
from onlinelinguisticdatabase.model.meta import Base, Session
from onlinelinguisticdatabase import model
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
    h.createOLDDirectories(config=config)

    # ISO-639-3 Language data for the languages table
    log.info("Retrieving ISO-639-3 languages data.")
    languages = h.getLanguageObjects(filename, config)

    # Get default users.
    log.info("Creating a default administrator, contributor and viewer.")
    administrator = h.generateDefaultAdministrator(configFilename=filename)
    contributor = h.generateDefaultContributor(configFilename=filename)
    viewer = h.generateDefaultViewer(configFilename=filename)

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
        requestsTestsPath = os.path.join(config['pylons.paths']['root'], 'tests',
                                         'scripts', '_requests_tests.py')
        copyfile(requestsTestsPath, '_requests_tests.py')

        # Create the tables if they don't already exist
        Base.metadata.create_all(bind=Session.bind, checkfirst=True)
        log.info('Tables created.')

        # Get default home & help pages.
        log.info("Creating default home and help pages.")
        homepage = h.generateDefaultHomePage()
        helppage = h.generateDefaultHelpPage()
    
        # Get default application settings.
        log.info("Generating default application settings.")
        applicationSettings = h.generateDefaultApplicationSettings()
    
        # Get default tags and categories
        log.info("Creating some useful tags and categories.")
        restrictedTag = h.generateRestrictedTag()
        foreignWordTag = h.generateForeignWordTag()
        S = h.generateSSyntacticCategory()
        N = h.generateNSyntacticCategory()
        V = h.generateVSyntacticCategory()
    
        # Initialize the database
        log.info("Adding defaults.")
        data = [administrator, contributor, viewer, homepage, helppage,
                applicationSettings, restrictedTag, foreignWordTag]
        if config['addLanguageData'] != '0':
            data += languages
        if config['emptyDatabase'] == '0':
            Session.add_all(data)
            Session.commit()
        log.info("OLD successfully set up.")
