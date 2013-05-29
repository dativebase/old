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

"""This executable toggles all nosetests in the onlinelinguisticdatabase/tests
directory on or off.

Usage:

Turn all of the tests in all of the test scripts on:

    $ ./_toggle_tests.py on

Turn all of the tests in all of the test scripts off:

    $ ./_toggle_tests.py off

Turn all of the tests in 'test_forms.py' and 'test_formsearches.py' off/on (note
that the .py extensions is optional):

    $ ./_toggle_tests.py on/off test_forms test_formsearches.py
"""

import os, sys, re


try:
    on_off = sys.argv[1]
    if on_off not in ('on', 'off'):
        on_off = None
except IndexError:
    on_off = None

tests_dir_path = os.path.dirname(os.path.realpath(__file__))

def add_py_suffix(fn):
    if fn.split('.')[-1] == 'py':
        return fn
    else:
        return '%s.py' % fn


def get_test_scripts():
    ignore_patt = re.compile('^(\.|_|setup\.py$)')
    scripts = os.listdir(tests_dir_path)
    return [s for s in scripts if not ignore_patt.search(s)]

files = [add_py_suffix(fn) for fn in sys.argv[2:]]


def toggle_tests_in_script(on_off, script):
    script_path = os.path.join(tests_dir_path, script)
    new_script_path = os.path.join(tests_dir_path, '%s.tmp' % script)
    script_file = open(script_path, 'r')
    new_script_file = open(new_script_path, 'w')
    test_me_patt = re.compile('^    #@nottest(\n| )')
    test_me_not_patt = re.compile('^    @nottest(\n| )')
    i = 1
    messages = []
    for line in script_file:
        if test_me_not_patt.search(line) and on_off == 'on':
            messages.append('Turned on test at line %d of %s.' % (i, script))
            new_script_file.write('    #@nottest\n')
        elif test_me_patt.search(line) and on_off == 'off':
            messages.append('Turned off test at line %d of %s.' % (i, script))
            new_script_file.write('    @nottest\n')
        else:
            new_script_file.write(line)
        i = i + 1
    new_script_file.close()
    script_file.close()
    if messages:
        os.rename(new_script_path, script_path)
    else:
        os.remove(new_script_path)
    return messages

if on_off is not None:
    test_scripts = get_test_scripts()
    if files == []:
        scripts_to_toggle = test_scripts
    else:
        scripts_to_toggle = list(set(test_scripts) & set(files))
    messages = [toggle_tests_in_script(on_off, script) for script in scripts_to_toggle]
    if sum([len(ms) for ms in messages]) == 0:
        print 'No tests were turned %s.' % on_off
    else:
        print '\n'.join(['\n'.join([m for m in ms]) for ms in messages if ms])
else:
    print 'You must specify "on" or "off" as the first argument.'