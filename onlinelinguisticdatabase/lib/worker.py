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

"""Worker thread and Queue for the OLD.

Worker threads are useful for executing long running tasks and returning to the
user immediately.

The worker can only run a callable that is a global in
:mod:`onlinelinguisticdatabase.lib.worker` and which takes keyword arguments. 
Example usage::

    from onlinelinguisticdatabase.lib.worker import worker_q
    worker_q.put({
        'id': h.generateSalt(),
        'func': 'compileFomaScript',
        'args': {'modelName': u'Phonology', 'modelId': phonology.id,
            'scriptDirPath': phonologyDirPath, 'userId': session['user'].id,
            'verificationString': u'defined phonology: ', 'timeout': h.phonologyCompileTimeout}
    })

Cf. http://www.chrismoos.com/2009/03/04/pylons-worker-threads.

For an introduction to Python threading, see
http://www.ibm.com/developerworks/aix/library/au-threadingpython/.

"""

import Queue
import threading
import logging
import os
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.model.meta import Session
import onlinelinguisticdatabase.model as model
from subprocess import Popen, PIPE
from signal import SIGKILL

log = logging.getLogger(__name__)

worker_q = Queue.Queue()

class WorkerThread(threading.Thread):
    """Define the worker."""
    def run(self):
        while True:
            msg = worker_q.get()
            try:
                globals()[msg.get('func')](**msg.get('args'))
            except Exception, e:
                log.warn('Unable to process in worker thread: ' + str(e))
            worker_q.task_done()

def start_worker():
    """Called in :mod:`onlinelinguisticdatabase.config.environment.py`."""
    worker = WorkerThread()
    worker.setDaemon(True)
    worker.start()


################################################################################
# Phonology Compile Functions
################################################################################

def getFilePath(modelObject, scriptDirPath, fileType='script'):
    """Return the path to a foma-based model's file of the given type.
    
    :param modelObject: a phonology or morphology model object.
    :param str scriptDirPath: the absolute path to the directory that houses the foma 
        script of the phonology or morphology
    :param str fileType: one of 'script', 'binary', 'compiler' or 'log'.
    :returns: an absolute path to the file of the supplied type for the model object given.

    """
    extMap = {'script': 'script', 'binary': 'foma', 'compiler': 'sh', 'log': 'log'}
    return os.path.join(scriptDirPath,
                '%s_%d.%s' % (modelObject.__tablename__, modelObject.id, extMap.get(fileType, 'script')))

def getPhonologyFilePath_(phonology, phonologyDirPath, fileType='script'):
    """Return the path to a phonology's file of the given type.
    
    :param phonology: a phonology model object.
    :param str phonologyDirPath: the absolute path to the phonology's directory.
    :param str fileType: one of 'script', 'binary' or 'compiler'.
    :returns: an absolute path to the phonology's script file.

    """
    extMap = {'script': 'script', 'binary': 'foma', 'compiler': 'sh', 'log': 'log'}
    return os.path.join(phonologyDirPath,
                        'phonology_%d.%s' % (phonology.id, extMap.get(fileType, 'script')))

class Command(object):
    """Runs the input command ``cmd`` as a subprocess within a thread.
    
    Pass a ``timeout`` argument to :func:`Command.run` and the process running
    the input ``cmd`` will be terminated at the end of that time if it hasn't
    terminated on its own.

    Cf. http://stackoverflow.com/questions/1191374/subprocess-with-timeout

    """
    def __init__(self, cmd, logpath=None):
        self.cmd = cmd
        self.logpath = logpath
        self.process = None

    def run(self, timeout):
        """Run :func:`self.cmd` as a subprocess that is terminated within ``timeout`` seconds.
        
        :param float timeout: time in seconds by which :func:`self.cmd` will be terminated.
        :return: 2-tuple: return code of process, stdout

        """
        def target():
            with open(self.logpath or os.devnull, "w") as logfile:
                self.process = Popen(self.cmd, stdout=logfile, stderr=logfile)
            self.process.communicate()
        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            self.killProcess(self.process)
            thread.join()
        try:
            stdout = open(self.logpath).read()
        except Exception:
            stdout = ''
        return self.process.returncode, stdout

    def killProcess(self, process):
        pid = process.pid
        pids = [pid]
        pids.extend(self.getProcessChildren(pid))
        for pid in pids:
            try: 
                os.kill(pid, SIGKILL)
            except OSError:
                pass

    def getProcessChildren(self, pid):
        p = Popen('ps --no-headers -o pid --ppid %d' % pid, shell=True,
                  stdout = PIPE, stderr = PIPE)
        stdout, stderr = p.communicate()
        return [int(p) for p in stdout.split()]

def compileFomaScript(**kwargs):
    """Compile the foma script of an OLD model (a phonology or a morphology).

    This function is called by the OLD worker.  It uses :class:`Command` to
    cancel the compilation if it exceeds ``timeout`` seconds.

    :param str kwargs['modelName']: the name of an OLD model, i.e., 'Phonology' or 'Morphology'.
    :param int kwargs['modelId']: a model's ``id`` value.
    :param str kwargs['scriptDirPath']: the absolute path to the model's script directory.
    :param int kwargs['userId']: a user model's ``id`` value.
    :param float/int kwargs['timeout']: how long to wait before terminating the compile process.
    :returns: ``None``
    :side effect: updates the values of the model object's ``datetimeCompiled``,
        ``compileSucceeded``, ``compileMessage``, ``modifier`` and
        ``datetimeModified`` attributes.

    """
    modelName = kwargs.get('modelName')
    modelId = kwargs.get('modelId')
    scriptDirPath = kwargs.get('scriptDirPath')
    userId = kwargs.get('userId')
    verificationString = kwargs.get('verificationString')
    timeout = kwargs.get('timeout', 30)
    try:
        modelObject = Session.query(getattr(model, modelName)).get(modelId)
        compilerPath = getFilePath(modelObject, scriptDirPath, 'compiler')
        binaryPath = getFilePath(modelObject, scriptDirPath, 'binary')
        logPath = getFilePath(modelObject, scriptDirPath, 'log')
        binaryMTime = h.getModificationTime(binaryPath)
        command = Command([compilerPath], logPath)
        returncode, output = command.run(timeout=timeout)
        if verificationString in output:
            if returncode == 0:
                if (os.path.isfile(binaryPath) and
                    binaryMTime != h.getModificationTime(binaryPath)):
                    modelObject.compileSucceeded = True
                    modelObject.compileMessage = u'Compilation process terminated successfully and new binary file was written.'
                else:
                    modelObject.compileSucceeded = False
                    modelObject.compileMessage = u'Compilation process terminated successfully yet no new binary file was written.'
            else:
                modelObject.compileSucceeded = False
                modelObject.compileMessage = u'Compilation process failed.'
        else:
            modelObject.compileSucceeded = False
            modelObject.compileMessage = u'Foma script is not a well-formed %s.' % modelName.lower()
    except Exception:
        modelObject.compileSucceeded = False
        modelObject.compileMessage = u'Compilation attempt raised an error.'
    if modelObject.compileSucceeded:
        os.chmod(binaryPath, 0744)
    else:
        try:
            os.remove(binaryPath)
        except Exception:
            pass
    now = h.now()
    modelObject.datetimeModified = now
    modelObject.datetimeCompiled = now
    modelObject.modifier_id = userId
    Session.commit()


def compilePhonologyScript_(phonologyId, phonologyDirPath, userId, timeout=30):
    """Compile the foma script of the phonology model.

    This function is called by the OLD worker.  It uses :class:`Command` to
    cancel the compilation if it exceeds ``timeout`` seconds.

    :param int phonologyId: a phonology model's ``id`` value.
    :param str phonologyDirPath: the path to the phonology's directory.
    :param int userId: a user model's ``id`` value.
    :param float timeout: how long to wait before terminating the compile process.
    :returns: ``None``
    :side effect: updates the values of the phonology's ``datetimeCompiled``,
        ``compileSucceeded``, ``compileMessage``, ``modifier`` and
        ``datetimeModified`` attributes.

    """
    try:
        phonology = Session.query(Phonology).get(phonologyId)
        phonologyCompilerPath = getPhonologyFilePath(phonology, phonologyDirPath, 'compiler')
        phonologyBinaryPath = getPhonologyFilePath(phonology, phonologyDirPath, 'binary')
        phonologyLogPath = getPhonologyFilePath(phonology, phonologyDirPath, 'log')
        phonologyBinaryMTime = h.getModificationTime(phonologyBinaryPath)
        command = Command([phonologyCompilerPath], phonologyLogPath)
        returncode, output = command.run(timeout=timeout)
        if 'defined phonology: ' in output:
            if returncode == 0:
                if (os.path.isfile(phonologyBinaryPath) and
                    phonologyBinaryMTime != h.getModificationTime(phonologyBinaryPath)):
                    phonology.compileSucceeded = True
                    phonology.compileMessage = u'Compilation process terminated successfully and new binary file was written.'
                else:
                    phonology.compileSucceeded = False
                    phonology.compileMessage = u'Compilation process terminated successfully yet no new binary file was written.'
            else:
                phonology.compileSucceeded = False
                phonology.compileMessage = u'Compilation process failed.'
        else:
            phonology.compileSucceeded = False
            phonology.compileMessage = u'Phonology script is not well-formed; maybe no "phonology" FST was defined (?).'
    except Exception, e:
        phonology.compileSucceeded = False
        phonology.compileMessage = u'Compilation attempt raised an error.'
    if phonology.compileSucceeded:
        os.chmod(phonologyBinaryPath, 0744)
    else:
        try:
            os.remove(phonologyBinaryPath)
        except Exception:
            pass
    now = h.now()
    phonology.datetimeModified = now
    phonology.datetimeCompiled = now
    phonology.modifier_id = userId
    Session.commit()
