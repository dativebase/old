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

"""This executable updates an OLD 0.2.7 MySQL database to one compatible with
the OLD 1.0a1.

Usage instructions:

    $ ./old_update_db_0.2.7_1.0a1.py mysql_db_name

Ensure that your MySQL server contains an OLD 0.2.7 database called 
``mysql_db_name``.  This script assumes that the directory from which
it is executed contains a Pylons config file with the same name as the 
database but with the ``.ini`` suffix.  This config file should contain 
the MySQL authorization information in the ``sqlalchemy.url`` line, e.g.,
``sqlalchemy.url = mysql://old:old@localhost:3306/old_test``.

Also ensure that the python environment has the OLD v. 1.0a1 installed.

"""

import os
import sys
import re
import subprocess
import datetime
from uuid import uuid4
from sqlalchemy import create_engine, MetaData, Table
from docutils.core import publish_parts
try:
    import json
except ImportError:
    import simplejson as json

# forms = Session.query(model.Form).all()
# etc. ...

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
-- TODO: deal with the backuper/modifier change (HARD!!!)
-- TODO: generate a UUID for each collectionbackup that matches
--  the appropriate collection (Python)
-- TODO: delete collectionbackup.backuper after post-Python
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

-- TODO: set filename to value of name, where appropriate (MySQL/Python?)
-- TODO: change the value of the url column to the URL that is inside the markup (Python).
-- TODO: potentially create lossy copies of files and add values to lossyFilename (Python).
ALTER TABLE file
    CONVERT TO CHARACTER SET utf8,
    ADD COLUMN filename VARCHAR(255) DEFAULT NULL,
    ADD COLUMN lossyFilename VARCHAR(255) DEFAULT NULL,
    MODIFY description TEXT,
    CHANGE embeddedFileMarkup url VARCHAR(255) DEFAULT NULL,
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

-- TODO: generate UUID values (Python)
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

-- TODO: deal with the backuper/modifier discrepancy and drop the backuper column. (Python)
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

-- TODO: how to make the name column unique? ADD INDEX (name)? ...
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

-- TODO: generate UUID values (Python)
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

-- TODO: generate a value for author using authorFirstName and authorLastName
--   and then delete those columns. (Python)
-- TODO: hand-parse the fullReference value and then drop the col.
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

-- TODO: generate values for the html field (Python).
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

-- TODO: generate a salt and a new password and hash the password (Python).
-- TODO: make sure roles are all valid ...
-- TODO: generate html values
-- TODO: populate the orthography relational attrs and delete the JSON ones
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
'''.strip()

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
'''.strip()

def getOrthographyReferenced(crappyReferenceString, row, orthographies):
    orthographyName = row['objectLanguageOrthography%sName' % crappyReferenceString.split()[-1]]
    return orthographies.get(orthographyName, None)

def rst2html(string):
    try:
        return publish_parts(string, writer_name='html')['html_body']
    except:
        return string

if __name__ == '__main__':

    # User must supply a valid ``mysql_db_name`` value
    try:
        mysql_db_name, mysql_username, mysql_password, mysql_dump_file = sys.argv[1:]
    except ValueError:
        mysql_db_name, mysql_username, mysql_password = sys.argv[1:]
    except Exception:
        sys.exit('Usage: ./old_update_db_0.2.7_1.0a1.py mysql_db_name, mysql_username, mysql_password')

    sqlalchemy_url = 'mysql://%s:%s@localhost:3306/%s?charset=utf8' % (mysql_username, mysql_password, mysql_db_name)
    engine = create_engine(sqlalchemy_url)
    meta = MetaData()

    # Some oft-used paths
    here = os.path.dirname(os.path.realpath(__file__))
    mysql_updater = os.path.join(here, 'tmp.sh')
    with open(mysql_updater, 'w') as f:
        pass
    os.chmod(mysql_updater, 0744)

    now = datetime.datetime.utcnow()
    now_string = now.isoformat().replace('T', ' ').split('.')[0]

    # Update script: runs a bunch of SQL to alter the tables
    mysql_update_script = os.path.join(here, 'old_update_db_0.2.7_1.0a1.sql')
    if not os.path.exists(mysql_update_script):
        with open(mysql_update_script, 'w') as f:
            f.write(update_SQL)
        os.chmod(mysql_update_script, 0744)

    # Clean up script: runs a bunch of SQL to clean up after the Pythonic alterations
    mysql_cleanup_script = os.path.join(here, 'old_cleanup_db_0.2.7_1.0a1.sql')
    if not os.path.exists(mysql_cleanup_script ):
        with open(mysql_cleanup_script , 'w') as f:
            f.write(cleanup_SQL)
        os.chmod(mysql_cleanup_script , 0744)

    # A second argument will be interpreted as the name of an OLD 0.2.7  mysql dump file.
    # If present, this script will delete the database named in the first argument,
    # recreate it and populate it with the data from the dump file named in the 
    # second argument
    try:
        script = [
            "#!/bin/sh",
            "mysql -u %s -p%s -e 'drop database %s;'" % (mysql_username, mysql_password, mysql_db_name),
            "mysql -u %s -p%s -e 'create database %s default character set utf8;'" % (mysql_username, mysql_password, mysql_db_name),
            "mysql -u %s -p%s %s < %s" % (mysql_username, mysql_password, mysql_db_name, mysql_dump_file),
        ]
        with open(mysql_updater, 'w') as f:
            f.write('\n'.join(script))
        with open(os.devnull, 'w') as devnull:
            subprocess.call([mysql_updater], shell=False, stdout=devnull, stderr=devnull)
    except NameError:
        pass

    # Update the database using the file created from the 
    # Create a shell script that runs the MySQL update script (old_update_db_0.2.7_1.0a1.sql),
    # run that shell script as a subprocess, then destroy the shell script
    mysql_script_content = '#!/bin/sh\nmysql -u %s -p%s %s < %s' % (mysql_username, mysql_password, mysql_db_name, mysql_update_script)
    with open(mysql_updater, 'w') as f:
        f.write(mysql_script_content)
    with open(os.devnull, 'w') as devnull:
        subprocess.call([mysql_updater], shell=False, stdout=devnull, stderr=devnull)

    ##################################################################################
    # Here is where we update the values of the newly modified database using Python
    ##################################################################################

    # Delete duplicate orthography records, i.e., remove all duplicates except that
    # with the highest id value.
    orthographies = engine.execute('SELECT id, name, orthography, lowercase, initialGlottalStops FROM orthography;').fetchall()
    tmp = {}
    for id, name, orthography, lowercase, initialGlottalStops in orthographies:
        tmp.setdefault((name, orthography, lowercase, initialGlottalStops), []).append(id)
    for k, v in tmp.items():
        idsToDelete = sorted(v)[:-1]
        if idsToDelete:
            engine.execute('DELETE FROM orthography WHERE id in (%s);' % ','.join(map(str, idsToDelete)))

    # Fix up the applicationsettings table

    # First get the orthographies as a dict from name to largest id
    orthographies = {}
    query = 'SELECT id, name FROM orthography;'
    result = engine.execute(query).fetchall()
    for id, name in result:
        orthographies.setdefault(name, []).append(id)
    for name, ids in orthographies.items():
        orthographies[name] = max(ids)

    # Now fix the orthography one-to-many relations and the many-to-many unrestrictedUsers relations
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
                engine.execute(
                    "INSERT INTO applicationsettingsuser (applicationsettings_id, user_id, datetimeModified) VALUES (%d, %d, '%s');" % (
                    row['id'], user_id, now_string))
        except Exception:
            pass

    # Fix up the collection table

    # REFERENCING_COLLECTIONS will hold a list of ids corresponding to collections that
    # will need to be manually updated in order to generate good contentsUnpacked values.
    collection = Table('collection', meta, autoload=True, autoload_with=engine)
    collectionReferencePattern = re.compile('[cC]ollection[\[\(](\d+)[\]\)]')
    REFERENCING_COLLECTIONS = []
    result = engine.execute('SELECT * from collection;')
    for row in result:
        cid = row['id']
        uuid = str(uuid4())
        html = rst2html(row['contents'])
        if collectionReferencePattern.search(row['contents']):
            REFERENCING_COLLECTIONS.append(cid)
        engine.execute(collection.update().where(collection.c.id==cid).values(UUID=uuid, html=html, contentsUnpacked=row['contents']))

    # Fix up the collectionbackup table
    # TODO: generate a UUID for each collectionbackup that matches the appropriate collection (Python)
    # TODO: generate an html value for each collectionbackup
    # TODO: deal with the backuper/modifier change (HARD!!!)
    # TODO: delete collectionbackup.backuper after post-Python

    collection.create: modifier is enterer
    collection.update: modifier is updater
    # Clean up the database by removing the extraneous columns
    # Create a shell script that runs the MySQL update script (old_update_db_0.2.7_1.0a1.sql),
    # run that shell script as a subprocess, then destroy the shell script
    mysql_script_content = '#!/bin/sh\nmysql -u %s -p%s %s < %s' % (mysql_username, mysql_password, mysql_db_name, mysql_cleanup_script)
    with open(mysql_updater, 'w') as f:
        f.write(mysql_script_content)
    with open(os.devnull, 'w') as devnull:
        subprocess.call([mysql_updater], shell=False, stdout=devnull, stderr=devnull)
    os.remove(mysql_updater)

    if REFERENCING_COLLECTIONS:
        print 'Collection(s) %s should be updated manually in order to generate valid contentsUnpacked values' % ', '.join(map(str, REFERENCING_COLLECTIONS))
    # TODO: make sure to check that the applicationsettings.unrestrictedUsers m-t-m value is set correctly
