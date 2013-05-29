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

The meta-function save_reduced_copy provides an interface to this functionality
that is used in the create action of the files controller.  It handles .wav and
image files appropriately and returns None for other file types.
"""

from paste.deploy.converters import asbool
from subprocess import call
from onlinelinguisticdatabase.lib.utils import ffmpeg_encodes, get_subprocess, get_OLD_directory_path
import os
try:
    import Image
except ImportError:
    pass

import logging
log = logging.getLogger(__name__)


def save_reduced_copy(file, config):
    """Save a smaller copy of the file in files/reduced_files.  Only works if
    the file is a .wav file or an image.  Returns None or the reduced file filename,
    depending on whether the reduction failed or succeeded, repectively.
    """
    if getattr(file, 'filename') and asbool(config.get('create_reduced_size_file_copies', 1)):
        files_path = get_OLD_directory_path('files', config=config['app_conf'])
        reduced_files_path = os.path.join(files_path, 'reduced_files')
        if u'image' in file.MIME_type:
            return save_reduced_size_image(file, files_path, reduced_files_path)
        elif file.MIME_type == u'audio/x-wav':
            format_ = config.get('preferred_lossy_audio_format', 'ogg')
            return save_wav_as(file, format_, files_path, reduced_files_path)
        else:
            return None
    return None

################################################################################
# Image Resizing using PIL
################################################################################

def save_reduced_size_image(file, files_path, reduced_files_path):
    """This function saves a size-reduced copy of the image to
    files/reduced_files.  Input is an OLD file model object.  Image formats are
    retained.  If the file is already shorter or narrower than size (defaults to
    500px x 500px), then no reduced copy is created and None is returned.  If
    successful, the name of the reduced image is returned.  None is returned if
    PIL is not installed.
    """
    try:
        in_path = os.path.join(files_path, file.filename)
        out_path = os.path.join(reduced_files_path, file.filename)
        size = 500, 500
        im = Image.open(in_path)
        if im.size[0] < size[0] or im.size[1] < size[1]:
            return None
        im.thumbnail(size, Image.ANTIALIAS)
        im.save(out_path)
        return file.filename
    except Exception, e:
        return None

################################################################################
# .wav-2-.ogg conversion using ffmpeg
################################################################################

def save_wav_as(file, format_, files_path, reduced_files_path):
    """Attempts to use ffmpeg to create a lossy copy of the contents of file in
    files/reduced_files according to the format (i.e., 'ogg' or 'mp3').
    """
    try:
        if not ffmpeg_encodes(format_):
            format_ = 'ogg'     # .ogg is the default
        if not ffmpeg_encodes(format_):
            return None
        else:
            in_path = os.path.join(files_path, file.filename)
            out_name = '%s.%s' % (os.path.splitext(file.filename)[0], format_)
            out_path = os.path.join(reduced_files_path, out_name)
            with open(os.devnull, "w") as fnull:
                result = call(['ffmpeg', '-i', in_path, out_path], stdout=fnull, stderr=fnull)
            if os.path.isfile(out_path):
                return out_name
            return None
    except Exception, e:
        return None
