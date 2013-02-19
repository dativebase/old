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

"""The resize module contains functionality for creating copies/versions of
image and audio files with reduced sizes.

1. Image resizing using PIL
2. wav-2-ogg conversion using ffmpeg

The meta-function saveReducedCopy provides an interface to this functionality
that is used in the create action of the files controller.  It handles .wav and
image files appropriately and returns None for other file types.
"""

from paste.deploy.converters import asbool
from subprocess import call
from onlinelinguisticdatabase.lib.utils import ffmpegEncodes, getSubprocess
import os
try:
    import Image
except ImportError:
    pass

import logging
log = logging.getLogger(__name__)


def saveReducedCopy(file, config):
    """Save a smaller copy of the file in files/reduced_files.  Only works if
    the file is a .wav file or an image.  Returns None or the reduced file filename,
    depending on whether the reduction failed or succeeded, repectively.
    """
    if getattr(file, 'filename') and asbool(config.get('create_reduced_size_file_copies', 1)):
        filesPath = config['app_conf']['permanent_store']
        reducedFilesPath = os.path.join(filesPath, 'reduced_files')
        if u'image' in file.MIMEtype:
            return saveReducedSizeImage(file, filesPath, reducedFilesPath)
        elif file.MIMEtype == u'audio/x-wav':
            format_ = config.get('preferred_lossy_audio_format', 'ogg')
            return saveWavAs(file, format_, filesPath, reducedFilesPath)
        else:
            return None
    return None

################################################################################
# Image Resizing using PIL
################################################################################

def saveReducedSizeImage(file, filesPath, reducedFilesPath):
    """This function saves a size-reduced copy of the image to
    files/reduced_files.  Input is an OLD file model object.  Image formats are
    retained.  If the file is already shorter or narrower than size (defaults to
    500px x 500px), then no reduced copy is created and None is returned.  If
    successful, the name of the reduced image is returned.  None is returned if
    PIL is not installed.
    """
    try:
        inPath = os.path.join(filesPath, file.filename)
        outPath = os.path.join(reducedFilesPath, file.filename)
        size = 500, 500
        im = Image.open(inPath)
        if im.size[0] < size[0] or im.size[1] < size[1]:
            return None
        im.thumbnail(size, Image.ANTIALIAS)
        im.save(outPath)
        return file.filename
    except:
        return None

################################################################################
# .wav-2-.ogg conversion using ffmpeg
################################################################################

def saveWavAs(file, format_, filesPath, reducedFilesPath):
    """Attempts to use ffmpeg to create a lossy copy of the contents of file in
    files/reduced_files according to the format (i.e., 'ogg' or 'mp3').
    """
    try:
        if not ffmpegEncodes(format_):
            format_ = 'ogg'     # .ogg is the default
        if not ffmpegEncodes(format_):
            return None
        else:
            inPath = os.path.join(filesPath, file.filename)
            outName = '%s.%s' % (os.path.splitext(file.filename)[0], format_)
            outPath = os.path.join(reducedFilesPath, outName)
            with open(os.devnull, "w") as fnull:
                result = call(['ffmpeg', '-i', inPath, outPath], stdout=fnull, stderr=fnull)
            if os.path.isfile(outPath):
                return outName
            return None
    except Exception, e:
        return None
