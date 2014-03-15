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

"""Basic command-line interface to a configured, compiled and exported OLD parser.

Usage:

    $ ./parse.py wordi (wordj ... wordn)

This script is intended to be included in the .zip archive returned by an OLD application
when GET /morphologicalparsers/id/export is requested on the fully generated and 
compiled morphological parser with id ``id``.  It expects all requisite files for the parser
and its sub-objects (e.g., the compiled morphophonology foma script, the pickled LM Trie, the
lexicon and dictionary pickle files, if needed, etc.) as well as a configuration pickle file
(i.e., config.pickle) to be present in the current working directory.

The code for the parser functionality is all located in ``parser.py``, which is the same as 
that used by an OLD web application.

Note that the included simplelm module is a somewhat modified version from that available at
<<URL>>.

"""

import os
import sys
import cPickle

# Alter the module search path so that the directory containing this script is in it.
# This is necessary for the importation of the local ``parser`` module.
script_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(script_dir)

import parser
if not 'PhonologyFST' in dir(parser):
    # Import the *local* parser module
    import imp
    parser_module_path = os.path.join(script_dir, 'parser.py')
    parser = imp.load_source(os.path.dirname(__file__), parser_module_path)

config_file = 'config.pickle'
config_path = os.path.join(script_dir, config_file)
config = cPickle.load(open(config_path, 'rb'))
cache_file = 'cache.pickle'
cache_path = os.path.join(script_dir, cache_file)

phonology = parser.PhonologyFST(
    parent_directory = script_dir,
    word_boundary_symbol = config['phonology']['word_boundary_symbol']
)

morphology = parser.MorphologyFST(
    parent_directory = script_dir,
    word_boundary_symbol = config['morphology']['word_boundary_symbol'],
    rare_delimiter = config['morphology']['rare_delimiter'],
    rich_upper = config['morphology']['rich_upper'],
    rich_lower = config['morphology']['rich_lower'],
    rules_generated = config['morphology']['rules_generated']
)

language_model = parser.LanguageModel(
    parent_directory = script_dir,
    rare_delimiter = config['language_model']['rare_delimiter'],
    start_symbol = config['language_model']['start_symbol'],
    end_symbol = config['language_model']['end_symbol'],
    categorial = config['language_model']['categorial']
)

parser = parser.MorphologicalParser(
    parent_directory = script_dir,
    word_boundary_symbol = config['parser']['word_boundary_symbol'],
    morpheme_delimiters = config['parser']['morpheme_delimiters'],
    phonology = phonology,
    morphology = morphology,
    language_model = language_model,
    cache = parser.Cache(path=cache_path)
)

if __name__ == '__main__':

    inputs = sys.argv[1:]
    for input_ in inputs:
        parse = parser.pretty_parse(input_)[input_]
        if parse:
            print u'%s %s' % (input_, u' '.join(parse))
        else:
            print u'%s No parse' % input_

