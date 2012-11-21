"""Setup the old application"""

import logging
import codecs
import datetime
import os

from old.config.environment import load_environment
from old.model import meta
from old import model
import old.lib.helpers as h

log = logging.getLogger(__name__)

def setup_app(command, conf, vars):
    """Place any commands to setup onlinelinguisticdatabase here"""

    config = load_environment(conf.global_conf, conf.local_conf)

    log.info('Environment loaded.')
    meta.metadata.bind = meta.engine
    filename = os.path.split(conf.filename)[-1] # e.g., production.ini, development.ini, test.ini, ...

    # Create the files directories.
    h.makeDirectorySafely('files')
    h.makeDirectorySafely(os.path.join('files', 'archived_files'))
    h.makeDirectorySafely(os.path.join('files', 'researchers'))

    # Create the analysis directories.
    h.makeDirectorySafely('analysis')
    h.makeDirectorySafely(os.path.join('analysis', 'phonology'))
    h.makeDirectorySafely(os.path.join('analysis', 'morphotactics'))
    h.makeDirectorySafely(os.path.join('analysis', 'morphophonology'))
    h.makeDirectorySafely(os.path.join('analysis', 'probabilitycalculator'))

    # ISO-639-3 Language data for the languages table
    log.info("Retrieving ISO-639-3 languages data.")
    languages = getLanguageObjects(filename, config)

    # Get default users.
    log.info("Creating a default administrator, contributor and viewer.")
    administrator = h.generateDefaultAdministrator(config)
    contributor = h.generateDefaultContributor(config)
    viewer = h.generateDefaultViewer(config)

    # If we are running tests, make sure the test db contains only language data.
    if filename == 'test.ini':
        # Permanently drop any existing tables
        meta.metadata.drop_all(checkfirst=True)
        log.info("Existing tables dropped.")

        # Create the tables if they don't already exist
        meta.metadata.create_all(checkfirst=True)
        log.info('Tables created.')

        meta.Session.add_all(languages + [administrator, contributor, viewer])
        meta.Session.commit()

    # Not a test: add a bunch of nice defaults.
    else:

        # Create the tables if they don't already exist
        meta.metadata.create_all(checkfirst=True)
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
            meta.Session.add_all(data)
            meta.Session.commit()
        log.info("OLD successfully set up.")

def getLanguageObjects(filename, config):
    languagesPath = os.path.join(config['pylons.paths']['root'], 'lib',
                                 'languages')
    # Use the truncated languages file if we are running tests
    if filename == 'test.ini':
        iso_639_3FilePath = os.path.join(languagesPath, 'iso_639_3_trunc.tab')
    else:
        iso_639_3FilePath = os.path.join(languagesPath, 'iso_639_3.tab')
    iso_639_3File = codecs.open(iso_639_3FilePath, 'r', 'utf-8')
    languageList = [l.split('\t') for l in iso_639_3File]
    return [getLanguageObject(language) for language in languageList
            if len(languageList) == 8]

def getLanguageObject(languageList):
    """Given a list of ISO-639-3 language data, return an OLD language model."""
    language = model.Language()
    language.Id = languageList[0]
    language.Part2B = languageList[1]
    language.Part2T = languageList[2]
    language.Part1 = languageList[3]
    language.Scope = languageList[4]
    language.Type = languageList[5]
    language.Ref_Name = languageList[6]
    language.Comment = languageList[7]
    return language