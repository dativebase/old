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

#!/usr/bin/python

"""This executable toggles all nosetests in the old/tests directory on or off.

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
    onOff = sys.argv[1]
    if onOff not in ('on', 'off'):
        onOff = None
except IndexError:
    onOff = None

testsDirPath = os.path.dirname(os.path.realpath(__file__))

def addPySuffix(fn):
    if fn.split('.')[-1] == 'py':
        return fn
    else:
        return '%s.py' % fn


def getTestScripts():
    ignorePatt = re.compile('^(\.|_|setup\.py$)')
    scripts = os.listdir(testsDirPath)
    return [s for s in scripts if not ignorePatt.search(s)]

files = [addPySuffix(fn) for fn in sys.argv[2:]]


def toggleTestsInScript(onOff, script):
    scriptPath = os.path.join(testsDirPath, script)
    newScriptPath = os.path.join(testsDirPath, '%s.tmp' % script)
    scriptFile = open(scriptPath, 'r')
    newScriptFile = open(newScriptPath, 'w')
    testMePatt = re.compile('^    #@nottest(\n| )')
    testMeNotPatt = re.compile('^    @nottest(\n| )')
    i = 1
    messages = []
    for line in scriptFile:
        if testMeNotPatt.search(line) and onOff == 'on':
            messages.append('Turned on test at line %d of %s.' % (i, script))
            newScriptFile.write('    #@nottest\n')
        elif testMePatt.search(line) and onOff == 'off':
            messages.append('Turned off test at line %d of %s.' % (i, script))
            newScriptFile.write('    @nottest\n')
        else:
            newScriptFile.write(line)
        i = i + 1
    newScriptFile.close()
    scriptFile.close()
    if messages:
        os.rename(newScriptPath, scriptPath)
    else:
        os.remove(newScriptPath)
    return messages

if onOff is not None:
    testScripts = getTestScripts()
    if files == []:
        scriptsToToggle = testScripts
    else:
        scriptsToToggle = list(set(testScripts) & set(files))
    messages = [toggleTestsInScript(onOff, script) for script in scriptsToToggle]
    if sum([len(ms) for ms in messages]) == 0:
        print 'No tests were turned %s.' % onOff
    else:
        print '\n'.join(['\n'.join([m for m in ms]) for ms in messages if ms])
else:
    print 'You must specify "on" or "off" as the first argument.'