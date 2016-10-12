# Copyright 2016 Joel Dunham
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

"""The application's Globals object.

"""

from apscheduler.schedulers.background import BackgroundScheduler
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options

class Globals(object):
    """Globals acts as a container for objects available throughout the life of
    the application.
    """

    def __init__(self, config):
        """One instance of Globals is created during application
        initialization and is available during requests via the
        'app_globals' variable.

        """
        self.cache = CacheManager(**parse_cache_config_options(config))
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

        # All the names of the resources defined via ``map.resource`` in
        # config/routing.py. Unfortunately, it appears that we cannot generate
        # these at runtime.
        self.resource_model_names = (
            'ApplicationSettings',
            'Collection',
            'CollectionBackup',
            'Corpus',
            'CorpusBackup',
            'ElicitationMethod',
            'File',
            'Form',
            'FormBackup',
            'FormSearch',
            'Keyboard',
            'Language',
            'MorphemeLanguageModel',
            'MorphemeLanguageModelBackup',
            'MorphologicalParser',
            'MorphologicalParserBackup',
            'Morphology',
            'MorphologyBackup',
            'Orthography',
            'Page',
            'Phonology',
            'PhonologyBackup',
            'Source',
            'Speaker',
            'SyncState',
            'SyntacticCategory',
            'Tag',
            'User',
        )
        self.version = '2.0.0'
