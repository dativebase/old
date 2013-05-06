#!/usr/bin/python

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

"""This executable updates an OLD 0.2.7 MySQL database and makes it compatible with
the OLD 1.0a1 data structure

Usage:

    $ ./old_update_db_0.2.7_1.0a1.py mysql_db_name mysql_username mysql_password [mysql_dump_file_path]

If the optional ``mysql_dump_file_path`` parameter is not supplied,
ensure that your MySQL server contains an OLD 0.2.7 database called 
``mysql_db_name``.  If the dump file path paramter is supplied, this script
will drop any database called ``mysql_db_name``, recreate it and populate it
with the data from the dump file.

"""

import os
import sys
import re
import string
import subprocess
import datetime
from random import choice, shuffle
from uuid import uuid4
from sqlalchemy import create_engine, MetaData, Table, bindparam
from docutils.core import publish_parts
from passlib.hash import pbkdf2_sha512
try:
    import json
except ImportError:
    import simplejson as json

# update_SQL holds the SQL statements that create the 1.0 tables missing in 0.2.7 and
# alter the existing tables.
update_SQL = '''
-- Create the applicationsettingsuser table
CREATE TABLE `applicationsettingsuser` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `applicationsettings_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `applicationsettings_id` (`applicationsettings_id`),
  KEY `user_id` (`user_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

-- Create the orthography table
CREATE TABLE `orthography` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `numberName` varchar(255) DEFAULT NULL,
  `orthography` text,
  `lowercase` tinyint(1) DEFAULT NULL,
  `initialGlottalStops` tinyint(1) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

-- Move the orthographies from application_settings to orthography
INSERT INTO orthography (name, orthography, lowercase,
    initialGlottalStops, datetimeModified)
    SELECT objectLanguageOrthography1Name,
        objectLanguageOrthography1,
        OLO1Lowercase,
        OLO1InitialGlottalStops,
        datetimeModified
    FROM application_settings 
    WHERE objectLanguageOrthography1 IS NOT NULL AND
        objectLanguageOrthography1 != '';
INSERT INTO orthography (name, orthography, lowercase,
    initialGlottalStops, datetimeModified)
    SELECT objectLanguageOrthography2Name,
        objectLanguageOrthography2,
        OLO2Lowercase,
        OLO2InitialGlottalStops,
        datetimeModified
    FROM application_settings 
    WHERE objectLanguageOrthography2 IS NOT NULL AND
        objectLanguageOrthography2 != '';
INSERT INTO orthography (name, orthography, lowercase,
    initialGlottalStops, datetimeModified)
    SELECT objectLanguageOrthography3Name,
        objectLanguageOrthography3,
        OLO3Lowercase,
        OLO3InitialGlottalStops,
        datetimeModified
    FROM application_settings 
    WHERE objectLanguageOrthography3 IS NOT NULL AND
        objectLanguageOrthography3 != '';
INSERT INTO orthography (name, orthography, lowercase,
    initialGlottalStops, datetimeModified)
    SELECT objectLanguageOrthography4Name,
        objectLanguageOrthography4,
        OLO4Lowercase,
        OLO4InitialGlottalStops,
        datetimeModified
    FROM application_settings 
    WHERE objectLanguageOrthography4 IS NOT NULL AND
        objectLanguageOrthography4 != '';
INSERT INTO orthography (name, orthography, lowercase,
    initialGlottalStops, datetimeModified)
    SELECT objectLanguageOrthography5Name,
        objectLanguageOrthography5,
        OLO5Lowercase,
        OLO5InitialGlottalStops,
        datetimeModified
    FROM application_settings 
    WHERE objectLanguageOrthography5 IS NOT NULL AND
        objectLanguageOrthography5 != '';

-- Modify the application_settings table as needed
RENAME TABLE application_settings TO applicationsettings;
UPDATE applicationsettings
    SET morphemeBreakIsObjectLanguageString=1
    WHERE morphemeBreakIsObjectLanguageString='yes';
UPDATE applicationsettings
    SET morphemeBreakIsObjectLanguageString=0
    WHERE morphemeBreakIsObjectLanguageString!='yes';
ALTER TABLE applicationsettings
    -- The following CONVERT clause may change TEXTs to MEDIUMTEXTS, cf. http://bugs.mysql.com/bug.php?id=31291
    CONVERT TO CHARACTER SET utf8,
    MODIFY objectLanguageId VARCHAR(3) DEFAULT NULL,
    MODIFY metalanguageId VARCHAR(3) DEFAULT NULL,
    MODIFY orthographicValidation VARCHAR(7) DEFAULT NULL,
    CHANGE metaLanguageOrthography metalanguageInventory TEXT,
    CHANGE punctuation punctuation TEXT,
    CHANGE metaLanguageName metalanguageName VARCHAR(255) DEFAULT NULL,
    CHANGE narrPhonInventory narrowPhoneticInventory TEXT,
    CHANGE narrPhonValidation narrowPhoneticValidation VARCHAR(7) DEFAULT NULL,
    CHANGE broadPhonInventory broadPhoneticInventory TEXT,
    CHANGE broadPhonValidation broadPhoneticValidation VARCHAR(7) DEFAULT NULL,
    CHANGE morphemeBreakIsObjectLanguageString morphemeBreakIsOrthographic tinyint(1) DEFAULT NULL,
    CHANGE morphPhonValidation morphemeBreakValidation VARCHAR(7) DEFAULT NULL,
    CHANGE morphPhonInventory phonemicInventory TEXT,
    CHANGE morphDelimiters morphemeDelimiters VARCHAR(255) DEFAULT NULL,
    DROP COLUMN headerImageName,
    DROP COLUMN colorsCSS,
    ADD storageOrthography_id int(11) DEFAULT NULL,
    ADD inputOrthography_id int(11) DEFAULT NULL,
    ADD outputOrthography_id int(11) DEFAULT NULL,
    ADD KEY (storageOrthography_id),
    ADD KEY (inputOrthography_id),
    ADD KEY (outputOrthography_id);

-- Change the collection table
ALTER TABLE collection
    CONVERT TO CHARACTER SET utf8,
    MODIFY contents TEXT,
    MODIFY description TEXT,
    ADD COLUMN UUID VARCHAR(36) DEFAULT NULL,
    ADD COLUMN markupLanguage VARCHAR(100) DEFAULT NULL,
    ADD COLUMN html TEXT,
    ADD COLUMN modifier_id INT(11) DEFAULT NULL,
    ADD COLUMN contentsUnpacked TEXT,
    ADD KEY (modifier_id);
UPDATE collection SET markupLanguage = 'restructuredText';

-- Change the collectionbackup TABLE
ALTER TABLE collectionbackup
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN UUID VARCHAR(36) DEFAULT NULL,
    ADD COLUMN markupLanguage VARCHAR(100) DEFAULT NULL,
    ADD COLUMN html TEXT,
    ADD COLUMN modifier TEXT,
    MODIFY speaker TEXT,
    MODIFY elicitor TEXT,
    MODIFY enterer TEXT,
    MODIFY description TEXT,
    MODIFY contents TEXT,
    MODIFY source TEXT,
    MODIFY files TEXT,
    ADD COLUMN forms TEXT,
    ADD COLUMN tags TEXT;
UPDATE collectionbackup SET markupLanguage = 'restructuredText';

ALTER TABLE collectionfile
    CONVERT TO CHARACTER SET utf8;

ALTER TABLE collectionform
    CONVERT TO CHARACTER SET utf8;

CREATE TABLE `collectiontag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `collection_id` int(11) DEFAULT NULL,
  `tag_id` int(11) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `collection_id` (`collection_id`),
  KEY `tag_id` (`tag_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `corpus` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `UUID` varchar(36) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `description` text,
  `content` longtext,
  `enterer_id` int(11) DEFAULT NULL,
  `modifier_id` int(11) DEFAULT NULL,
  `formSearch_id` int(11) DEFAULT NULL,
  `datetimeEntered` datetime DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `enterer_id` (`enterer_id`),
  KEY `modifier_id` (`modifier_id`),
  KEY `formSearch_id` (`formSearch_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `corpusbackup` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `corpus_id` int(11) DEFAULT NULL,
  `UUID` varchar(36) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `type` varchar(255) DEFAULT NULL,
  `description` text,
  `content` longtext,
  `enterer` text,
  `modifier` text,
  `formSearch` text,
  `datetimeEntered` datetime DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  `tags` text,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `corpusfile` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `corpus_id` int(11) DEFAULT NULL,
  `filename` varchar(255) DEFAULT NULL,
  `format` varchar(255) DEFAULT NULL,
  `creator_id` int(11) DEFAULT NULL,
  `modifier_id` int(11) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  `datetimeCreated` datetime DEFAULT NULL,
  `restricted` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `corpus_id` (`corpus_id`),
  KEY `creator_id` (`creator_id`),
  KEY `modifier_id` (`modifier_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `corpusform` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `corpus_id` int(11) DEFAULT NULL,
  `form_id` int(11) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `corpus_id` (`corpus_id`),
  KEY `form_id` (`form_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `corpustag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `corpus_id` int(11) DEFAULT NULL,
  `tag_id` int(11) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `corpus_id` (`corpus_id`),
  KEY `tag_id` (`tag_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

ALTER TABLE elicitationmethod
    CONVERT TO CHARACTER SET utf8,
    MODIFY description TEXT;

ALTER TABLE file
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN filename VARCHAR(255) DEFAULT NULL,
    ADD COLUMN lossyFilename VARCHAR(255) DEFAULT NULL,
    MODIFY description TEXT,
    CHANGE embeddedFileMarkup url TEXT,
    CHANGE embeddedFilePassword password VARCHAR(255) DEFAULT NULL,
    ADD COLUMN parentFile_id INT(11) DEFAULT NULL,
    ADD COLUMN start FLOAT DEFAULT NULL,
    ADD COLUMN end FLOAT DEFAULT NULL,
    ADD KEY (parentFile_id);

CREATE TABLE `filetag` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `file_id` int(11) DEFAULT NULL,
  `tag_id` int(11) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `file_id` (`file_id`),
  KEY `tag_id` (`tag_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

ALTER TABLE form
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN UUID VARCHAR(36) DEFAULT NULL,
    MODIFY comments TEXT,
    MODIFY speakerComments TEXT,
    MODIFY morphemeBreakIDs TEXT,
    MODIFY morphemeGlossIDs TEXT,
    ADD COLUMN syntax VARCHAR(1023) DEFAULT NULL,
    ADD COLUMN semantics VARCHAR(1023) DEFAULT NULL,
    ADD COLUMN status VARCHAR(40) DEFAULT NULL,
    ADD COLUMN modifier_id INT(11) DEFAULT NULL,
    ADD KEY (modifier_id);
UPDATE form SET status='tested';

ALTER TABLE formbackup
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN UUID VARCHAR(36) DEFAULT NULL,
    MODIFY comments TEXT,
    MODIFY speakerComments TEXT,
    MODIFY morphemeBreakIDs TEXT,
    MODIFY morphemeGlossIDs TEXT,
    MODIFY elicitor TEXT,
    MODIFY enterer TEXT,
    MODIFY verifier TEXT,
    MODIFY speaker TEXT,
    MODIFY elicitationMethod TEXT,
    MODIFY syntacticCategory TEXT,
    MODIFY source TEXT,
    MODIFY files TEXT,
    CHANGE keywords tags TEXT,
    CHANGE glosses translations TEXT,
    ADD COLUMN syntax VARCHAR(1023) DEFAULT NULL,
    ADD COLUMN semantics VARCHAR(1023) DEFAULT NULL,
    ADD COLUMN modifier TEXT;

ALTER TABLE formfile
    CONVERT TO CHARACTER SET utf8;

CREATE TABLE `formsearch` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `search` text,
  `description` text,
  `enterer_id` int(11) DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `enterer_id` (`enterer_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

RENAME TABLE formkeyword TO formtag;
ALTER TABLE formtag
    CONVERT TO CHARACTER SET utf8,
    CHANGE keyword_id tag_id INT(11) DEFAULT NULL,
    ADD KEY (tag_id);

RENAME TABLE gloss TO translation;
ALTER TABLE translation
    CONVERT TO CHARACTER SET utf8,
    CHANGE gloss transcription TEXT NOT NULL,
    CHANGE glossGrammaticality grammaticality VARCHAR(255) DEFAULT NULL;

RENAME TABLE keyword TO tag;
ALTER TABLE tag
    CONVERT TO CHARACTER SET utf8,
    MODIFY description TEXT;

ALTER TABLE language
    CONVERT TO CHARACTER SET utf8;

CREATE TABLE `morphology` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `UUID` varchar(36) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `description` text,
  `script` longtext,
  `lexiconCorpus_id` int(11) DEFAULT NULL,
  `rulesCorpus_id` int(11) DEFAULT NULL,
  `enterer_id` int(11) DEFAULT NULL,
  `modifier_id` int(11) DEFAULT NULL,
  `datetimeEntered` datetime DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  `datetimeCompiled` datetime DEFAULT NULL,
  `compileSucceeded` tinyint(1) DEFAULT NULL,
  `compileMessage` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `lexiconCorpus_id` (`lexiconCorpus_id`),
  KEY `rulesCorpus_id` (`rulesCorpus_id`),
  KEY `enterer_id` (`enterer_id`),
  KEY `modifier_id` (`modifier_id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

CREATE TABLE `morphologybackup` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `morphology_id` int(11) DEFAULT NULL,
  `UUID` varchar(36) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `description` text,
  `script` longtext,
  `lexiconCorpus` text,
  `rulesCorpus` text,
  `enterer` text,
  `modifier` text,
  `datetimeEntered` datetime DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  `datetimeCompiled` datetime DEFAULT NULL,
  `compileSucceeded` tinyint(1) DEFAULT NULL,
  `compileMessage` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

ALTER TABLE page
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN html TEXT,
    CHANGE markup markupLanguage VARCHAR(100) DEFAULT NULL,
    MODIFY content TEXT;
UPDATE page SET markupLanguage='restructuredText';

ALTER TABLE phonology
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN UUID VARCHAR(36) DEFAULT NULL,
    MODIFY description TEXT,
    MODIFY script TEXT,
    ADD COLUMN datetimeCompiled datetime DEFAULT NULL,
    ADD COLUMN compileSucceeded tinyint(1) DEFAULT NULL,
    ADD COLUMN compileMessage VARCHAR(255) DEFAULT NULL;

CREATE TABLE `phonologybackup` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `phonology_id` int(11) DEFAULT NULL,
  `UUID` varchar(36) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `description` text,
  `script` text,
  `enterer` text,
  `modifier` text,
  `datetimeEntered` datetime DEFAULT NULL,
  `datetimeModified` datetime DEFAULT NULL,
  `datetimeCompiled` datetime DEFAULT NULL,
  `compileSucceeded` tinyint(1) DEFAULT NULL,
  `compileMessage` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

ALTER TABLE source
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN `crossrefSource_id` int(11) DEFAULT NULL,
    ADD COLUMN `type` varchar(20) DEFAULT NULL,
    ADD COLUMN `key` varchar(1000) DEFAULT NULL,
    ADD COLUMN `address` varchar(1000) DEFAULT NULL,
    ADD COLUMN `annote` text,
    ADD COLUMN `author` varchar(255) DEFAULT NULL,
    ADD COLUMN `booktitle` varchar(255) DEFAULT NULL,
    ADD COLUMN `chapter` varchar(255) DEFAULT NULL,
    ADD COLUMN `crossref` varchar(1000) DEFAULT NULL,
    ADD COLUMN `edition` varchar(255) DEFAULT NULL,
    ADD COLUMN `editor` varchar(255) DEFAULT NULL,
    ADD COLUMN `howpublished` varchar(255) DEFAULT NULL,
    ADD COLUMN `institution` varchar(255) DEFAULT NULL,
    ADD COLUMN `journal` varchar(255) DEFAULT NULL,
    ADD COLUMN `keyField` varchar(255) DEFAULT NULL,
    ADD COLUMN `month` varchar(100) DEFAULT NULL,
    ADD COLUMN `note` varchar(1000) DEFAULT NULL,
    ADD COLUMN `number` varchar(100) DEFAULT NULL,
    ADD COLUMN `organization` varchar(255) DEFAULT NULL,
    ADD COLUMN `pages` varchar(100) DEFAULT NULL,
    ADD COLUMN `publisher` varchar(255) DEFAULT NULL,
    ADD COLUMN `school` varchar(255) DEFAULT NULL,
    ADD COLUMN `series` varchar(255) DEFAULT NULL,
    ADD COLUMN `typeField` varchar(255) DEFAULT NULL,
    ADD COLUMN `url` varchar(1000) DEFAULT NULL,
    ADD COLUMN `volume` varchar(100) DEFAULT NULL,
    ADD COLUMN `affiliation` varchar(255) DEFAULT NULL,
    ADD COLUMN `abstract` varchar(1000) DEFAULT NULL,
    ADD COLUMN `contents` varchar(255) DEFAULT NULL,
    ADD COLUMN `copyright` varchar(255) DEFAULT NULL,
    ADD COLUMN `ISBN` varchar(20) DEFAULT NULL,
    ADD COLUMN `ISSN` varchar(20) DEFAULT NULL,
    ADD COLUMN `keywords` varchar(255) DEFAULT NULL,
    ADD COLUMN `language` varchar(255) DEFAULT NULL,
    ADD COLUMN `location` varchar(255) DEFAULT NULL,
    ADD COLUMN `LCCN` varchar(20) DEFAULT NULL,
    ADD COLUMN `mrnumber` varchar(25) DEFAULT NULL,
    ADD COLUMN `price` varchar(100) DEFAULT NULL,
    ADD COLUMN `size` varchar(255) DEFAULT NULL,
    ADD KEY (crossrefSource_id);

ALTER TABLE speaker
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN markupLanguage VARCHAR(100) DEFAULT NULL,
    CHANGE speakerPageContent pageContent TEXT,
    ADD COLUMN html TEXT;
UPDATE speaker SET markupLanguage='restructuredText';

ALTER TABLE syntacticcategory
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN `type` VARCHAR(60) DEFAULT NULL,
    MODIFY description TEXT;

ALTER TABLE `user`
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN salt VARCHAR(255) DEFAULT NULL,
    MODIFY role VARCHAR(100) DEFAULT NULL,
    ADD COLUMN markupLanguage VARCHAR(100) DEFAULT NULL,
    CHANGE personalPageContent pageContent TEXT,
    ADD COLUMN html TEXT,
    ADD COLUMN inputOrthography_id INT(11) DEFAULT NULL,
    ADD COLUMN outputOrthography_id INT(11) DEFAULT NULL,
    ADD KEY (inputOrthography_id),
    ADD KEY (outputOrthography_id);
UPDATE user SET markupLanguage='restructuredText';

ALTER TABLE userform
    CONVERT TO CHARACTER SET utf8;

'''.strip()

def write_update_executable(mysql_update_script_name, here):
    """Write the contents of update_SQL to an executable and return the path to it."""
    mysql_update_script = os.path.join(here, mysql_update_script_name)
    if not os.path.exists(mysql_update_script):
        with open(mysql_update_script, 'w') as f:
            f.write(update_SQL)
        os.chmod(mysql_update_script, 0744)
    return mysql_update_script

# cleanup_SQL performs the final modifications on the database, dropping 
# the columns that were retained in update_SQL.
cleanup_SQL = '''
ALTER TABLE applicationsettings
    DROP COLUMN objectLanguageOrthography1Name,
    DROP COLUMN objectLanguageOrthography1,
    DROP COLUMN OLO1Lowercase,
    DROP COLUMN OLO1InitialGlottalStops,
    DROP COLUMN objectLanguageOrthography2Name,
    DROP COLUMN objectLanguageOrthography2,
    DROP COLUMN OLO2Lowercase,
    DROP COLUMN OLO2InitialGlottalStops,
    DROP COLUMN objectLanguageOrthography3Name,
    DROP COLUMN objectLanguageOrthography3,
    DROP COLUMN OLO3Lowercase,
    DROP COLUMN OLO3InitialGlottalStops,
    DROP COLUMN objectLanguageOrthography4Name,
    DROP COLUMN objectLanguageOrthography4,
    DROP COLUMN OLO4Lowercase,
    DROP COLUMN OLO4InitialGlottalStops,
    DROP COLUMN objectLanguageOrthography5Name,
    DROP COLUMN objectLanguageOrthography5,
    DROP COLUMN OLO5Lowercase,
    DROP COLUMN OLO5InitialGlottalStops,
    DROP COLUMN storageOrthography,
    DROP COLUMN defaultInputOrthography,
    DROP COLUMN defaultOutputOrthography,
    DROP COLUMN unrestrictedUsers;

ALTER TABLE collectionbackup
    DROP COLUMN backuper;

ALTER TABLE file
    MODIFY url VARCHAR(255) DEFAULT NULL;

ALTER TABLE formbackup
    DROP COLUMN backuper;

ALTER TABLE source
    DROP COLUMN authorFirstName,
    DROP COLUMN authorLastName,
    DROP COLUMN fullReference;

ALTER TABLE user
    DROP COLUMN inputOrthography,
    DROP COLUMN outputOrthography;

'''.strip()

def print_(string):
    sys.stdout.write(string)
    sys.stdout.flush()

def write_cleanup_executable(mysql_cleanup_script_name, here):
    """Write the contents of cleanup_SQL to an executable and return the path to it."""
    mysql_cleanup_script = os.path.join(here, mysql_cleanup_script_name)
    if not os.path.exists(mysql_cleanup_script ):
        with open(mysql_cleanup_script , 'w') as f:
            f.write(cleanup_SQL)
        os.chmod(mysql_cleanup_script , 0744)
    return mysql_cleanup_script

def write_charset_executable(mysql_charset_script_name, here):
    """Write to disk as an executable the file that will be used to issue the MySQL
    statements that change the character set to UTF-8 -- return the absolute path.
    """
    mysql_charset_script = os.path.join(here, mysql_charset_script_name)
    if not os.path.exists(mysql_charset_script):
        with open(mysql_charset_script, 'w') as f:
            pass
        os.chmod(mysql_charset_script, 0744)
    return mysql_charset_script

def write_updater_executable(mysql_updater_name, here):
    """Write to disk the shell script that will be used to load the various MySQL scripts.
    Return the absolute path.
    """
    mysql_updater = os.path.join(here, mysql_updater_name)
    with open(mysql_updater, 'w') as f:
        pass
    os.chmod(mysql_updater, 0744)
    return mysql_updater

def recreate_database(mysql_db_name, mysql_dump_file, mysql_username, mysql_password, mysql_updater):
    """Drop the database `mysql_db_name` and recreate it using the MySQL dump file.
    """
    print_('Dropping database %s, recreating it and loading the data from the dump file %s ... ' % (mysql_db_name, mysql_dump_file))
    script = [
        "#!/bin/sh",
        "mysql -u %s -p%s -e 'drop database %s;'" % (mysql_username, mysql_password, mysql_db_name),
        "mysql -u %s -p%s -e 'create database %s;'" % (mysql_username, mysql_password, mysql_db_name),
        "mysql -u %s -p%s %s < %s" % (mysql_username, mysql_password, mysql_db_name, mysql_dump_file),
    ]
    with open(mysql_updater, 'w') as f:
        f.write('\n'.join(script))
    with open(os.devnull, 'w') as devnull:
        subprocess.call([mysql_updater], shell=False, stdout=devnull, stderr=devnull)
    print 'done.'

def get_non_utf8_tables_columns(mysql_db_name, mysql_username, mysql_password):
    """Return two lists: the names of tables and columns that do not use the UTF-8 character set."""
    sqlalchemy_url = 'mysql://%s:%s@localhost:3306/information_schema' % (mysql_username, mysql_password)
    info_schema_engine = create_engine(sqlalchemy_url)
    tables_table = Table('TABLES', meta, autoload=True, autoload_with=info_schema_engine)
    columns_table = Table('COLUMNS', meta, autoload=True, autoload_with=info_schema_engine)
    select = tables_table.select().\
        where(tables_table.c.TABLE_SCHEMA == bindparam('mysql_db_name')).\
        where(tables_table.c.TABLE_COLLATION != 'utf8_general_ci')
    non_utf8_tables = [row['TABLE_NAME'] for row in 
            info_schema_engine.execute(select, {'mysql_db_name': mysql_db_name}).fetchall()]
    select = columns_table.select().\
        where(columns_table.c.TABLE_SCHEMA == bindparam('mysql_db_name')).\
        where(columns_table.c.COLLATION_NAME != 'utf8_general_ci')
    non_utf8_columns = [row['COLUMN_NAME'] for row in 
            info_schema_engine.execute(select, {'mysql_db_name': mysql_db_name}).fetchall()]
    return non_utf8_tables, non_utf8_columns

def get_columns_with_collations(mysql_db_name, mysql_username, mysql_password):
    """Return a dict whose keys are table names and whose values are tuples representing 
    columns of the relevant table that have collations, i.e., TEXT and VARCHAR type columns.
    """
    tables = {}
    sqlalchemy_url = 'mysql://%s:%s@localhost:3306/information_schema' % (mysql_username, mysql_password)
    info_schema_engine = create_engine(sqlalchemy_url)
    columns_table = Table('COLUMNS', meta, autoload=True, autoload_with=info_schema_engine)
    select = columns_table.select().\
        where(columns_table.c.TABLE_SCHEMA == bindparam('mysql_db_name')).\
        where(columns_table.c.COLLATION_NAME != None)
    for row in info_schema_engine.execute(select, {'mysql_db_name': mysql_db_name}):
        tables.setdefault(row['table_name'], []).append((row['column_name'], row['column_type'], row['column_key']))
    return tables

def write_charset_executable_content(mysql_charset_script, columns_with_collations, mysql_db_name):
    """Write a series of MySQL commands to the file at mysql_charset_script; these commands will alter
    the tables and columns (and the db) so that they use the UTF-8 character set.
    """
    with open(mysql_charset_script, 'w') as f:
        for table_name, columns in columns_with_collations.items():
            indices = [(cn, ck) for cn, ct, ck in columns if ck]
            f.write('ALTER TABLE %s\n' % table_name)
            if indices:
                for cn, ck in indices:
                    if ck == 'PRI':
                        f.write('  DROP PRIMARY KEY,\n')
                    else:
                        f.write('  DROP INDEX %s,\n' % cn)
            f.write('  %s;\n\n' % ',\n  '.join(['CHANGE `%s` `%s` BLOB' % (cn, cn) for cn, ct, ck in columns]))
        for table_name, columns in columns_with_collations.items():
            indices = [(cn, ck) for cn, ct, ck in columns if ck]
            f.write('ALTER TABLE %s\n' % table_name)
            f.write('  %s' % ',\n  '.join(['CHANGE `%s` `%s` %s CHARACTER SET utf8' % (cn, cn, ct) for cn, ct, ck in columns]))
            if indices:
                f.write(',\n')
                for index, (cn, ck) in enumerate(indices):
                    if ck == 'PRI':
                        f.write('  ADD INDEX (`%s`)' % cn)
                    else:
                        f.write('  ADD UNIQUE (`%s`)' % cn)
                    if index == len(indices) - 1:
                        f.write(';\n\n')
                    else:
                        f.write(',\n')
            else:
                f.write(';\n\n')
        for table_name in columns_with_collations:
            f.write('ALTER TABLE %s DEFAULT CHARACTER SET utf8;\n\n' % table_name)
        f.write('ALTER DATABASE %s DEFAULT CHARACTER SET utf8;\n' % mysql_db_name)

def change_db_charset_to_utf8(mysql_db_name, mysql_charset_script, mysql_username, mysql_password, mysql_updater):
    """Run the executable ast `mysql_charset_script` in order to change the character set of the db to UTF-8."""
    print_('Changing the character set of the database to UTF-8 ... ')
    columns_with_collations = get_columns_with_collations(mysql_db_name, mysql_username, mysql_password)
    write_charset_executable_content(mysql_charset_script, columns_with_collations, mysql_db_name)
    script = [
        "#!/bin/sh",
        "mysql -u %s -p%s %s < %s" % (mysql_username, mysql_password, mysql_db_name, mysql_charset_script),
    ]
    with open(mysql_updater, 'w') as f:
        f.write('\n'.join(script))
    with open(os.devnull, 'w') as devnull:
        subprocess.call([mysql_updater], shell=False, stdout=devnull, stderr=devnull)
    print 'done.'

def perform_preliminary_update(mysql_db_name, mysql_update_script, mysql_username, mysql_password, mysql_updater):
    """Perform the preliminary update of the db by calling the executable at ``mysql_update_script``."""
    print_('Running the MySQL update script ... ')
    mysql_script_content = '#!/bin/sh\nmysql -u %s -p%s %s < %s' % (mysql_username, mysql_password, mysql_db_name, mysql_update_script)
    with open(mysql_updater, 'w') as f:
        f.write(mysql_script_content)
    with open(os.devnull, 'w') as devnull:
        subprocess.call([mysql_updater], shell=False, stdout=devnull, stderr=devnull)
    print 'done.'

def delete_duplicate_orthographies(engine):
    """Make sure that all orthographies are unique based on the values of name, orthography, lowercase and initialGlottalStops."""
    print_('Fixing the orthography table ... ')
    orthographies = engine.execute('SELECT id, name, orthography, lowercase, initialGlottalStops FROM orthography;').fetchall()
    tmp = {}
    for id, name, orthography, lowercase, initialGlottalStops in orthographies:
        tmp.setdefault((name, orthography, lowercase, initialGlottalStops), []).append(id)
    for k, v in tmp.items():
        idsToDelete = sorted(v)[:-1]
        if idsToDelete:
            engine.execute('DELETE FROM orthography WHERE id in (%s);' % ','.join(map(str, idsToDelete)))
    print 'done.'

def get_orthographies_by_name(engine):
    """Return a dict form orthography names to the largest id corresponding to an orthography with that name."""
    orthographies = {}
    query = 'SELECT id, name FROM orthography;'
    result = engine.execute(query).fetchall()
    for id, name in result:
        orthographies.setdefault(name, []).append(id)
    for name, ids in orthographies.items():
        orthographies[name] = max(ids)
    return orthographies

def fix_application_settings_table(engine, user_table, now_string):
    """Fix the applicationsettings table: create the orthography and unrestrictedUsers relations.

    :param dict orthographies: the dict from orthography names to ids as generated by ``get_orthographies_by_name``.

    """
    print_('Fixing the applicationsettings table ... ')
    msgs = []
    orthographies = get_orthographies_by_name(engine)
    users = engine.execute(user_table.select()).fetchall()
    user_ids = [u['id'] for u in users]
    query = 'SELECT * FROM applicationsettings;'
    result = engine.execute(query)
    for row in result:
        # Convert the orthography references by name to foreign key id references
        if row['storageOrthography']:
            orthography_id = getOrthographyReferenced(row['storageOrthography'], row, orthographies)
            if orthography_id:
                engine.execute('UPDATE applicationsettings SET storageOrthography_id=%d WHERE id=%s' % (orthography_id, row['id']))
        if row['defaultInputOrthography']:
            orthography_id = getOrthographyReferenced(row['defaultInputOrthography'], row, orthographies)
            if orthography_id:
                engine.execute('UPDATE applicationsettings SET inputOrthography_id=%d WHERE id=%s' % (orthography_id, row['id']))
        if row['defaultOutputOrthography']:
            orthography_id = getOrthographyReferenced(row['defaultOutputOrthography'], row, orthographies)
            if orthography_id:
                engine.execute('UPDATE applicationsettings SET outputOrthography_id=%d WHERE id=%s' % (orthography_id, row['id']))
        try:
            unrestricted_user_ids = json.loads(row['unrestrictedUsers'])
            for user_id in unrestricted_user_ids:
                if user_id in user_ids:
                    engine.execute(
                        "INSERT INTO applicationsettingsuser (applicationsettings_id, user_id, datetimeModified) VALUES (%d, %d, '%s');" % (
                        row['id'], user_id, now_string))
                else:
                    msgs.append('WARNING: user %d was listed as unrestricted but this user does not exist.\n' % user_id)
        except Exception:
            pass
    print 'done.'
    return msgs

def fix_user_table(engine, user_table):
    """Generate new values for password, salt, html, inputOrthography_id and outputOrthography_id."""
    print_('Fixing the user table ... ')
    msgs = []
    orthographies = get_orthographies_by_name(engine)
    try:
        current_application_settings = engine.execute('SELECT * FROM applicationsettings ORDER BY id DESC LIMIT 1;').fetchall()[0]
    except Exception:
        current_application_settings = None
    buffer1 = []
    for row in engine.execute(user_table.select()):
        lastName = row['lastName']
        firstName = row['firstName']
        values = {'u_id': row['id'], 'html': rst2html(row['pageContent']), 'salt': generateSalt()}
        new_password = generatePassword()
        values['password'] = encryptPassword(new_password, values['salt'])
        msgs.append('User %d (%s %s) now has the password %s' % (row['id'], firstName, lastName, new_password))
        if row['role'] not in ('administrator', 'contributor', 'viewer'):
            msgs.append('User %d (%s %s) has an invalid role: %s' % (row['id'], firstName, lastName, row['role']))
        values['inputOrthography_id'] = values['outputOrthography_id'] = None
        if current_application_settings:
            if row['inputOrthography']:
                orthography_name = current_application_settings['objectLanguageOrthography%sName' % row['inputOrthography'].split()[-1]]
                values['inputOrthography_id'] = orthographies.get(orthography_name, None)
            if row['outputOrthography']:
                orthography_name = current_application_settings['objectLanguageOrthography%sName' % row['outputOrthography'].split()[-1]]
                values['outputOrthography_id'] = orthographies.get(orthography_name, None)
        buffer1.append(values)
    update = user_table.update().where(user_table.c.id==bindparam('u_id')).\
            values(html=bindparam('html'), salt=bindparam('salt'), password=bindparam('password'),
                    inputOrthography_id=bindparam('inputOrthography_id'), outputOrthography_id=bindparam('outputOrthography_id'))
    engine.execute(update, buffer1)
    print 'done.'
    return msgs

def fix_collection_table(engine, collection_table, collectionbackup_table, user_table):
    """Add UUID, html, contentsUnpacked and modifier_id values to the collections.  Also,
    add UUID values to the backups of each collection.  Return a list of collection ids corresponding
    to those that reference other collections.

    .. note:: 

        There is a somewhat nasty complication that arises because of a change
        in how backupers/modifiers are recorded with backups.  In the OLD 0.2.7, every
        time a backup occurs, the backuper value of the backup is set to the user who
        made the backup and this information is not stored in the original.  In the OLD 1.0,
        creates, updates and deletes all set the modifier value to the user who performed
        the action and then this info is copied to the modifier value of the backup.  Thus we
        must perform the following transformations:

        for collection in collections:
            if collection has a backuper
                then it has been updated, so we should
                set its modifier to the user referenced in the backuper attribute of its most recent backuper
            else
                then it was created but never updated or deleted, so we should
                set its modifier to its enterer
        for collectionbackup in collectionbackups:
            if there are older backups of the same collection
                then set the modifier of the present collectionbackup to the backuper value of the most recent such sister backup
        else
            this is the first backup and its modifier should be its enterer

    """
    print_('Fixing the collection table ... ')
    collectionReferencePattern = re.compile('[cC]ollection[\[\(](\d+)[\]\)]')
    msgs = []
    users = engine.execute(user_table.select()).fetchall()
    collectionbackups = engine.execute(collectionbackup_table.select()).fetchall()
    buffer1 = []
    buffer2 = []
    for row in engine.execute(collection_table.select()):
        values = {'c_id': row['id'], 'UUID': str(uuid4()), 'html': rst2html(row['contents']).encode('utf8'),
                  'contentsUnpacked': row['contents']}
        backups = sorted([cb for cb in collectionbackups if cb['collection_id'] == row['id']],
                         key=lambda cb: cb['datetimeModified'])
        if backups:
            try:
                most_recent_backuper = json.loads(backups[-1]['backuper'])['id']
                if [u for u in users if u['id'] == most_recent_backuper]:
                    values['modifier_id'] = most_recent_backuper
                else:
                    values['modifier_id'] = row['enterer_id']
                    msgs.append('WARNING: there is no user with id %d to be the most recent backuper for for collection %d' % (most_recent_backuper, row['id']))
            except Exception:
                msgs.append('''WARNING: there are %d backups for collection %d; however,
it was not possible to extract a backuper from the most recent one (backuper value: %s)'''.replace('\n', ' ') % (
                        len(backups), row['id'], backups[-1]['backuper']))
                values['modifier_id'] = row['enterer_id']
        else:
            values['modifier_id'] = row['enterer_id']
        if collectionReferencePattern.search(row['contents']):
            msgs.append('''WARNING: collection %d references other collections; please update this collection via the
OLD interface in order to generate appropriate html and contentsUnpacked values.''' % row['id'])
        buffer1.append(values)
        for cb in backups:
            buffer2.append({'cb_id': cb['id'], 'UUID': values['UUID']})
    update = collection_table.update().where(collection_table.c.id==bindparam('c_id')).\
                values(UUID=bindparam('UUID'), html=bindparam('html'), contentsUnpacked=bindparam('contentsUnpacked'),
                       modifier_id=bindparam('modifier_id'))
    engine.execute(update, buffer1)
    update = collectionbackup_table.update().where(collectionbackup_table.c.id==bindparam('cb_id')).\
                values(UUID=bindparam('UUID'))
    engine.execute(update, buffer2)
    print 'done.'
    return msgs

def fix_collectionbackup_table(engine, collectionbackup_table):
    """Add html, modifier and (potentially) UUID values to the collections backups."""
    print_('Fixing the collectionbackup table ... ')
    uuidless = {} # maps collection ids to UUIDs
    collectionbackups = engine.execute(collectionbackup_table.select()).fetchall()
    buffer1 = []
    buffer2 = []
    for row in collectionbackups:
        values = {'cb_id': row['id'], 'html': rst2html(row['contents']).encode('utf8')}
        backups = sorted([cb for cb in collectionbackups if cb['collection_id'] == row['collection_id']],
                         key=lambda cb: cb['datetimeModified'])
        if backups:
            most_recent_backuper = backups[-1]['backuper']
            values['modifier'] = most_recent_backuper
        else:
            values['modifier'] = row['enterer']
        # Any cbs without UUID values must be from deleted collections
        if row['UUID'] is None:
            uuid = uuidless.get(row['collection_id'], uuid4())
            uuidless[row['collection_id']] = uuid
            values['UUID'] = uuid
            buffer1.append(values)
        else:
            buffer2.append(values)
    update = collectionbackup_table.update().where(collectionbackup_table.c.id==bindparam('cb_id')).\
                values(html=bindparam('html'), modifier=bindparam('modifier'), UUID=bindparam('UUID'))
    engine.execute(update, buffer1)
    update = collectionbackup_table.update().where(collectionbackup_table.c.id==bindparam('cb_id')).\
                values(html=bindparam('html'), modifier=bindparam('modifier'))
    engine.execute(update, buffer2)
    print 'done.'

def fix_file_table(engine, file_table):
    """Fix the file table: if the file has a url value, append it to the description 
    value and delete it from the url value; otherwise, set the filename value to the name value.
    """
    print_('Fixing the file table ... ')
    msgs = []
    files = engine.execute(file_table.select()).fetchall()
    buffer1 = []
    buffer2 = []
    for row in files:
        values = {'f_id': row['id']}
        if row['url']:
            values['url'] = ''
            values['description'] = '%s %s' % (row['description'], row['url'])
            messages.append('WARNING: the url/embeddedFileMarkup value of file %d has been appended \
                    to its description value.  Please alter this file by hand so that it has \
                    an appropriate url value' % row['id'])
            buffer1.append(values)
        else:
            values['filename'] = row['name']
            buffer2.append(values)
    update = file_table.update().where(file_table.c.id==bindparam('f_id')).\
                values(url=bindparam('url'), description=bindparam('description'))
    engine.execute(update, buffer1)
    update = file_table.update().where(file_table.c.id==bindparam('f_id')).\
                values(filename=bindparam('filename'))
    engine.execute(update, buffer2)
    print 'done.'
    return msgs

def fix_form_table(engine, form_table, formbackup_table, user_table):
    """Give UUID, modifier_id values to the form table.  Also give UUID values to
    all form backups that are backups of existing forms.

    .. note::

        There is a somewhat nasty complication that arises because of a change
        in how backupers/modifiers are recorded with backups.  In the OLD 0.2.7, every 
        time a backup occurs, the backuper value of the backup is set to the user who
        made the backup and this information is not stored in the original.  In the OLD 1.0,
        creates, updates and deletes all set the modifier value to the user who performed
        the action and then this info is copied to the modifier value of the backup.  Thus we
        must perform the following transformations:
        for form in forms:
            if forms has a backuper
                then it has been updated, so we should
                set its modifier to the user referenced in the backuper attribute of its most recent backuper
            else
                then it was created but never updated or deleted, so we should
                set its modifier to its enterer
        for formbackup in formbackups:
            if there are older backups of the same form
                then set the modifier of the present formbackup to the backuper value of the most recent such sister backup
        else
            this is the first backup and its modifier should be its enterer

    """
    print_('Fixing the form table ... ')
    msgs = []
    users = engine.execute(user_table.select()).fetchall()
    formbackups = engine.execute(formbackup_table.select()).fetchall()
    form_update_cache = []
    formbackup_update_cache = []
    for row in engine.execute(form_table.select()):
        values = {'f_id': row['id'], 'UUID': str(uuid4())}
        backups = sorted([fb for fb in formbackups if fb['form_id'] == row['id']],
                         key=lambda fb: fb['datetimeModified'])
        if backups:
            try:
                most_recent_backuper = json.loads(backups[-1]['backuper'])['id']
                if [u for u in users if u['id'] == most_recent_backuper]:
                    values['modifier_id'] = most_recent_backuper
                else:
                    values['modifier_id'] = row['enterer_id']
                    msgs.append('WARNING: there is no user %d to serve as the most recent backuper for form %d' % (most_recent_backuper, row['id']))
            except Exception:
                msgs.append('''WARNING: there are %d backups for form %d; however,
it was not possible to extract a backuper from the most recent one (backuper value: %s)'''.replace('\n', ' ') % (
                        len(backups), row['id'], backups[-1]['backuper']))
                values['modifier_id'] = row['enterer_id']
        else:
            values['modifier_id'] = row['enterer_id']
        form_update_cache.append(values)
        for fb in backups:
            formbackup_update_cache.append({'fb_id': fb['id'], 'UUID': values['UUID']})
    update = form_table.update().where(form_table.c.id==bindparam('f_id')).values(UUID=bindparam('UUID'), modifier_id=bindparam('modifier_id'))
    engine.execute(update, form_update_cache)
    update = formbackup_table.update().where(formbackup_table.c.id==bindparam('fb_id')).values(UUID=bindparam('UUID'))
    engine.execute(update, formbackup_update_cache)
    print 'done.'
    return msgs

def fix_formbackup_table(engine, formbackup_table):
    """Give each form a modifier value and (potentially) a UUID value also (if it doesn't have one)."""
    print_('Fixing the formbackup table ... ')
    uuidless = {} # maps form ids to UUIDs
    buffer1 = []
    buffer2 = []
    formbackups = engine.execute(formbackup_table.select()).fetchall()
    for row in formbackups:
        values = {'fb_id': row['id']}
        backups = sorted([fb for fb in formbackups if fb['form_id'] == row['form_id']],
                         key=lambda fb: fb['datetimeModified'])
        if backups:
            most_recent_backuper = backups[-1]['backuper']
            values['modifier'] = most_recent_backuper
        else:
            values['modifier'] = row['enterer']
        if row['UUID'] is None:
            uuid = uuidless.get(row['form_id'], uuid4())
            uuidless[row['form_id']] = uuid
            values['UUID'] = uuid
        if values.get('UUID', None):
            buffer2.append(values)
        else:
            buffer1.append(values)
    update = formbackup_table.update().where(formbackup_table.c.id==bindparam('fb_id')).values(modifier=bindparam('modifier'))
    engine.execute(update, buffer1)
    update = formbackup_table.update().where(formbackup_table.c.id==bindparam('fb_id')).\
                values(modifier=bindparam('modifier'), UUID=bindparam('UUID'))
    engine.execute(update, buffer2)
    print 'done.'

def fix_phonology_table(engine, phonology_table, phonologybackup_table, user_table):
    """Give each phonology UUID and modifier_id values; also give the phonology backups of
    existing phonologies UUID values.

    """
    print_('Fixing the phonology table ... ')
    msgs = []
    users = engine.execute(user_table.select()).fetchall()
    phonologybackups = engine.execute(phonologybackup_table.select()).fetchall()
    buffer1 = []
    buffer2 = []
    for row in engine.execute(phonology_table.select()):
        values = {'p_id': row['id'], 'UUID': str(uuid4())}
        backups = sorted([pb for pb in phonologybackups if pb['phonology_id'] == row['id']],
                         key=lambda pb: pb['datetimeModified'])
        if backups:
            try:
                most_recent_backuper = json.loads(backups[-1]['backuper'])['id']
                if [u for u in users if u['id'] == most_recent_backuper]:
                    values['modifier_id'] = most_recent_backuper
                else:
                    values['modifier_id'] = row['enterer_id']
                    msgs.append('There is no user %d to serve as the most recent backuper for phonology %d' % (most_recent_backuper, row['id']))
            except Exception:
                msgs.append('''WARNING: there are %d backups for phonology %d; however,
it was not possible to extract a backuper from the most recent one (backuper value: %s)'''.replace('\n', ' ') % (
                        len(backups), row['id'], backups[-1]['backuper']))
                values['modifier_id'] = row['enterer_id']
        else:
            values['modifier_id'] = row['enterer_id']
        buffer1.append(values)
        for pb in backups:
            buffer2.append({'pb_id': pb['id'], 'UUID': values['UUID']})
    update = phonologybackup_table.update().where(phonologybackup_table.c.id==bindparam('pb_id')).\
            values(UUID=bindparam('UUID'))
    engine.execute(update, buffer2)
    update = phonology_table.update().where(phonology_table.c.id==bindparam('p_id')).\
            values(modifier_id=bindparam('modifier_id'), UUID=bindparam('UUID'))
    engine.execute(update, buffer1)
    print 'done.'
    return msgs

def fix_phonologybackup_table(engine, phonologybackup_table):
    """Provide each phonology backup with a modifier value and (potentially) a UUID value too."""
    print_('Fixing the phonologybackup table ... ')
    uuidless = {} # maps phonology ids to UUIDs
    buffer1 = []
    buffer2 = []
    phonologybackups = engine.execute(phonologybackup_table.select()).fetchall()
    for row in phonologybackups:
        values = {'pb_id': row['id']}
        backups = sorted([pb for pb in phonologybackups if pb['phonology_id'] == row['phonology_id']],
                         key=lambda pb: pb['datetimeModified'])
        if backups:
            most_recent_backuper = backups[-1]['backuper']
            values['modifier'] = most_recent_backuper
        else:
            values['modifier'] = row['enterer']
        if row['UUID'] is None:
            uuid = uuidless.get(row['phonology_id'], uuid4())
            uuidless[row['phonology_id']] = uuid
            values['UUID'] = uuid
        if 'UUID' in values:
            buffer2.append(values)
        else:
            buffer1.append(values)
    update = phonologybackup_table.update().where(phonologybackup_table.c.id==bindparam('pb_id')).\
            values(UUID=bindparam('UUID'), modifier=bindparam('modifier'))
    engine.execute(update, buffer2)
    update = phonologybackup_table.update().where(phonologybackup_table.c.id==bindparam('pb_id')).\
            values(modifier=bindparam('modifier'))
    engine.execute(update, buffer1)
    print 'done.'

def find_duplicate_tags(engine, tag_table):
    """Warn the user about duplicate tags."""
    print_('Checking for duplicate tag names ... ')
    msgs = []
    tags = [row['name'] for row in engine.execute(tag_table.select()).fetchall()]
    duplicate_tags = set([x for x in tags if len([y for y in tags if y == x]) > 1])
    for dt in duplicate_tags:
        msgs.append('There is more than one tag named "%s"; please manually change the name of one of them.' % dt)
    print 'done.'
    return msgs

def fix_source_table(engine, source_table):
    """Create an author value and put the fullReference value in the annote field.
    Return a message explaining what was done.
    """
    print_('Fixing the source table ... ')
    buffer1 = []
    for row in engine.execute(source_table.select()):
        values = {'s_id': row['id']}
        first_name = row['authorFirstName']
        last_name = row['authorLastName']
        if first_name and last_name:
            author = '%s %s' % (first_name, last_name)
        else:
            author = None
        values['author'] = author
        values['annote'] = row['fullReference']
        buffer1.append(values)
    update = source_table.update().where(source_table.c.id==bindparam('s_id')).\
            values(author = bindparam('author'), annote = bindparam('annote'))
    engine.execute(update, buffer1)
    print 'done.'
    return ['''Sources have been updated.
An author value was constructed using the authorFirstName and authorLastName values.
The fullReference value was moved to the annote attribute.
The soures will need to be updated manually.'''.replace('\n', ' ')]

def fix_speaker_table(engine, speaker_table):
    """Generate an html value for each speaker."""
    print_('Fixing the speaker table ... ')
    buffer1 = []
    for row in engine.execute(speaker_table.select()):
        buffer1.append({'s_id': row['id'], 'html': rst2html(row['pageContent']).encode('utf8')})
    update = speaker_table.update().where(speaker_table.c.id==bindparam('s_id')).\
            values(html=bindparam('html'))
    engine.execute(update, buffer1)
    print 'done.'

def cleanup_db(mysql_db_name, mysql_cleanup_script, mysql_updater, mysql_username, mysql_password):
    """Run the MySQL cleanup script against the db (cf. cleanup_SQL for the contents of this script)."""
    print_('Cleaning up ... ')
    mysql_script_content = '#!/bin/sh\nmysql -u %s -p%s %s < %s' % (mysql_username, mysql_password, mysql_db_name, mysql_cleanup_script)
    with open(mysql_updater, 'w') as f:
        f.write(mysql_script_content)
    with open(os.devnull, 'w') as devnull:
        subprocess.call([mysql_updater], shell=False, stdout=devnull, stderr=devnull)
    print 'done.'

def getOrthographyReferenced(crappyReferenceString, row, orthographies):
    """Return the id of the orthography model referenced in ``crappyReferenceString``.
    ``crappyReferenceString`` is something like "Orthography 1" or "Object Language Orthography 3"
    and ``row`` is a row in the applicationsettings table.  ``orthographies`` is a dict from
    orthography names to orthography ids.

    """
    orthographyName = row['objectLanguageOrthography%sName' % crappyReferenceString.split()[-1]]
    return orthographies.get(orthographyName, None)

def rst2html(string):
    """Covert a restructuredText string to HTML."""
    try:
        return publish_parts(string, writer_name='html', settings_overrides={'report_level':'quiet'})['html_body']
    except:
        return string

def generateSalt():
    return str(uuid4().hex)

def encryptPassword(password, salt):
    """Use PassLib's pbkdf2 implementation to generate a hash from a password.
    Cf. http://packages.python.org/passlib/lib/passlib.hash.pbkdf2_digest.html#passlib.hash.pbkdf2_sha512
    """
    return pbkdf2_sha512.encrypt(password, salt=salt)

def generatePassword(length=12):
    """Generate a random password containing 3 UC letters, 3 LC ones, 3 digits and 3 symbols."""
    lcLetters = string.letters[:26]
    ucLetters = string.letters[26:]
    digits = string.digits
    symbols = string.punctuation.replace('\\', '')
    password = [choice(lcLetters) for i in range(3)] + \
               [choice(ucLetters) for i in range(3)] + \
               [choice(digits) for i in range(3)] + \
               [choice(symbols) for i in range(3)]
    shuffle(password)
    return ''.join(password)

url_re = re.compile('''='(http://[^ ]+)'|="(http://[^ ]+)"''')

def extractURLFromHTML(string):
    urls = sorted([x[0] or x[1] for x in url_re.findall(string)], key=len)
    return ' '.join(urls)


if __name__ == '__main__':

    # User must supply values for mysql_db_name, mysql_username and mysql_password.
    # A value for the path to a MySQL dump file (absolute or relative to cwd) is optional.
    mysql_dump_file = None
    try:
        mysql_db_name, mysql_username, mysql_password, mysql_dump_file = sys.argv[1:]
    except ValueError:
        mysql_db_name, mysql_username, mysql_password = sys.argv[1:]
    except Exception:
        sys.exit('Usage: ./old_update_db_0.2.7_1.0a1.py mysql_db_name, mysql_username, mysql_password')

    # The SQLAlchemy/MySQLdb/MySQL connection objects
    sqlalchemy_url = 'mysql://%s:%s@localhost:3306/%s' % (mysql_username, mysql_password, mysql_db_name)
    engine = create_engine(sqlalchemy_url)
    try:
        engine.execute('SELECT COUNT(id) FROM user;').fetchall()
    except Exception:
        sys.exit('Error: the MySQL database name, username and password are not valid.')
    meta = MetaData()

    now = datetime.datetime.utcnow()
    now_string = now.isoformat().replace('T', ' ').split('.')[0]
    here = os.path.dirname(os.path.realpath(__file__))

    # The shell script that will be used multiple times to load the MySQL scripts below
    mysql_updater_name = 'tmp.sh'
    mysql_updater = write_updater_executable(mysql_updater_name, here)

    # The executable that does the preliminary update
    mysql_update_script_name = 'old_update_db_0.2.7_1.0a1.sql'
    mysql_update_script = write_update_executable(mysql_update_script_name, here)

    # The executable that fixes the character set
    mysql_charset_script_name = 'old_charset_db_0.2.7_1.0a1.sql'
    mysql_charset_script = write_charset_executable(mysql_charset_script_name, here)

    # The executable that performs the final clean up
    mysql_cleanup_script_name = 'old_cleanup_db_0.2.7_1.0a1.sql'
    mysql_cleanup_script = write_cleanup_executable(mysql_cleanup_script_name, here)

    # If a dump file path was provided, recreate the db using it and change the character set to UTF-8
    if mysql_dump_file:
        if os.path.isfile(mysql_dump_file):
            recreate_database(mysql_db_name, mysql_dump_file, mysql_username, mysql_password, mysql_updater)
            change_db_charset_to_utf8(mysql_db_name, mysql_charset_script, mysql_username, mysql_password, mysql_updater)
        else:
            sys.exit('Error: there is no such dump file %s' % os.path.join(os.getcwd(), mysql_dump_file))

    # Perform the preliminary update of the database using ``mysql_update_script``
    perform_preliminary_update(mysql_db_name, mysql_update_script, mysql_username, mysql_password, mysql_updater)

    ##################################################################################
    # Now we update the values of the newly modified database Pythonically
    ##################################################################################

    collection_table = Table('collection', meta, autoload=True, autoload_with=engine)
    collectionbackup_table = Table('collectionbackup', meta, autoload=True, autoload_with=engine)
    file_table = Table('file', meta, autoload=True, autoload_with=engine)
    form_table = Table('form', meta, autoload=True, autoload_with=engine)
    formbackup_table = Table('formbackup', meta, autoload=True, autoload_with=engine)
    phonology_table = Table('phonology', meta, autoload=True, autoload_with=engine)
    phonologybackup_table = Table('phonologybackup', meta, autoload=True, autoload_with=engine)
    source_table = Table('source', meta, autoload=True, autoload_with=engine)
    speaker_table = Table('speaker', meta, autoload=True, autoload_with=engine)
    tag_table = Table('tag', meta, autoload=True, autoload_with=engine)
    user_table= Table('user', meta, autoload=True, autoload_with=engine)

    messages = []
    delete_duplicate_orthographies(engine)
    messages += fix_application_settings_table(engine, user_table, now_string)
    messages += fix_user_table(engine, user_table)
    messages += fix_collection_table(engine, collection_table, collectionbackup_table, user_table)
    fix_collectionbackup_table(engine, collectionbackup_table)
    messages += fix_file_table(engine, file_table)
    messages += fix_form_table(engine, form_table, formbackup_table, user_table)
    fix_formbackup_table(engine, formbackup_table)
    messages += fix_phonology_table(engine, phonology_table, phonologybackup_table, user_table)
    fix_phonologybackup_table(engine, phonologybackup_table)
    messages += find_duplicate_tags(engine, tag_table)
    messages += fix_source_table(engine, source_table)
    fix_speaker_table(engine, speaker_table)
    cleanup_db(mysql_db_name, mysql_cleanup_script, mysql_updater, mysql_username, mysql_password)
    os.remove(mysql_updater)
    print 'OK'

    print '\n\n%s' % '\n\n'.join(messages)

    # TODO: make sure to check that the applicationsettings.unrestrictedUsers m-t-m value is set correctly
    # TODO: what to do about files without lossy copies?  A separate script to create them?
    # TODO: compile morphemic analysis on the forms ... yuch
    # TODO: dump the unchanged data from the database before and after and run a diff to make sure
    #       nothing has changed.

