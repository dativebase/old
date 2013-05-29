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

"""Contains the :class:`PhonologiesController` and its auxiliary functions.

.. module:: phonologies
   :synopsis: Contains the phonologies controller and its auxiliary functions.

"""

import logging
import simplejson as json
import os
from uuid import uuid4
import codecs
from subprocess import Popen
from paste.fileapp import FileApp
from pylons.controllers.util import forward
from shutil import rmtree
from pylons import request, response, session, config
from formencode.validators import Invalid
from onlinelinguisticdatabase.lib.base import BaseController
from onlinelinguisticdatabase.lib.schemata import PhonologySchema, MorphophonemicTranscriptionsSchema
import onlinelinguisticdatabase.lib.helpers as h
from onlinelinguisticdatabase.lib.SQLAQueryBuilder import SQLAQueryBuilder
from onlinelinguisticdatabase.model.meta import Session
from onlinelinguisticdatabase.model import Phonology, PhonologyBackup
from onlinelinguisticdatabase.lib.foma_worker import foma_worker_q

log = logging.getLogger(__name__)

class PhonologiesController(BaseController):
    """Generate responses to requests on phonology resources.

    REST Controller styled on the Atom Publishing Protocol.

    .. note::
    
       The ``h.jsonify`` decorator converts the return value of the methods to
       JSON.

    """

    query_builder = SQLAQueryBuilder('Phonology', config=config)

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def index(self):
        """Get all phonology resources.

        :URL: ``GET /phonologies`` with optional query string parameters for
            ordering and pagination.
        :returns: a list of all phonology resources.

        .. note::

           See :func:`utils.add_order_by` and :func:`utils.add_pagination` for the
           query string parameters that effect ordering and pagination.

        """
        try:
            query = h.eagerload_phonology(Session.query(Phonology))
            query = h.add_order_by(query, dict(request.GET), self.query_builder)
            return h.add_pagination(query, dict(request.GET))
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('POST')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def create(self):
        """Create a new phonology resource and return it.

        :URL: ``POST /phonologies``
        :request body: JSON object representing the phonology to create.
        :returns: the newly created phonology.

        """
        try:
            schema = PhonologySchema()
            values = json.loads(unicode(request.body, request.charset))
            data = schema.to_python(values)
            phonology = create_new_phonology(data)
            Session.add(phonology)
            Session.commit()
            save_phonology_script(phonology)
            return phonology
        except h.JSONDecodeError:
            response.status_int = 400
            return h.JSONDecodeErrorResponse
        except Invalid, e:
            response.status_int = 400
            return {'errors': e.unpack_errors()}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def new(self):
        """Return the data necessary to create a new phonology.

        :URL: ``GET /phonologies/new``.
        :returns: an empty dictionary.

        """
        return {}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def update(self, id):
        """Update a phonology and return it.
        
        :URL: ``PUT /phonologies/id``
        :Request body: JSON object representing the phonology with updated attribute values.
        :param str id: the ``id`` value of the phonology to be updated.
        :returns: the updated phonology model.

        """
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(int(id))
        if phonology:
            try:
                schema = PhonologySchema()
                values = json.loads(unicode(request.body, request.charset))
                state = h.get_state_object(values)
                state.id = id
                data = schema.to_python(values, state)
                phonology_dict = phonology.get_dict()
                phonology = update_phonology(phonology, data)
                # phonology will be False if there are no changes (cf. update_phonology).
                if phonology:
                    backup_phonology(phonology_dict)
                    Session.add(phonology)
                    Session.commit()
                    save_phonology_script(phonology)
                    return phonology
                else:
                    response.status_int = 400
                    return {'error':
                        u'The update request failed because the submitted data were not new.'}
            except h.JSONDecodeError:
                response.status_int = 400
                return h.JSONDecodeErrorResponse
            except Invalid, e:
                response.status_int = 400
                return {'errors': e.unpack_errors()}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('DELETE')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def delete(self, id):
        """Delete an existing phonology and return it.

        :URL: ``DELETE /phonologies/id``
        :param str id: the ``id`` value of the phonology to be deleted.
        :returns: the deleted phonology model.

        """
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(id)
        if phonology:
            phonology_dict = phonology.get_dict()
            backup_phonology(phonology_dict)
            Session.delete(phonology)
            Session.commit()
            remove_phonology_directory(phonology)
            return phonology
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def show(self, id):
        """Return a phonology.
        
        :URL: ``GET /phonologies/id``
        :param str id: the ``id`` value of the phonology to be returned.
        :returns: a phonology model object.

        """
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(id)
        if phonology:
            return phonology
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def edit(self, id):
        """Return a phonology and the data needed to update it.

        :URL: ``GET /phonologies/edit``
        :param str id: the ``id`` value of the phonology that will be updated.
        :returns: a dictionary of the form::

                {"phonology": {...}, "data": {...}}

            where the value of the ``phonology`` key is a dictionary
            representation of the phonology and the value of the ``data`` key
            is an empty dictionary.

        """
        phonology = h.eagerload_phonology(Session.query(Phonology)).get(id)
        if phonology:
            return {'data': {}, 'phonology': phonology}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    def history(self, id):
        """Return the phonology with ``phonology.id==id`` and its previous versions.

        :URL: ``GET /phonologies/history/id``
        :param str id: a string matching the ``id`` or ``UUID`` value of the
            phonology whose history is requested.
        :returns: A dictionary of the form::

                {"phonology": { ... }, "previous_versions": [ ... ]}

            where the value of the ``phonology`` key is the phonology whose
            history is requested and the value of the ``previous_versions`` key
            is a list of dictionaries representing previous versions of the
            phonology.

        """
        phonology, previous_versions = h.get_model_and_previous_versions('Phonology', id)
        if phonology or previous_versions:
            return {'phonology': phonology,
                    'previous_versions': previous_versions}
        else:
            response.status_int = 404
            return {'error': 'No phonologies or phonology backups match %s' % id}

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def compile(self, id):
        """Compile the script of a phonology as a foma FST.

        :URL: ``PUT /phonologies/compile/id``
        :param str id: the ``id`` value of the phonology whose script will be compiled.
        :returns: if the phonology exists and foma is installed, the phonology
            model is returned;  ``GET /phonologies/id`` must be polled to
            determine when and how the compilation task has terminated.

        .. note::

            The script is compiled asynchronously in a worker thread.  See 
            :mod:`onlinelinguisticdatabase.lib.foma_worker`.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.foma_installed():
                phonology_dir_path = get_phonology_dir_path(phonology)
                foma_worker_q.put({
                    'id': h.generate_salt(),
                    'func': 'compile_phonology_script',
                    'args': {'phonology_id': phonology.id, 'script_dir_path': phonology_dir_path,
                        'user_id': session['user'].id, 'verification_string': u'defined phonology: ',
                        'timeout': h.phonology_compile_timeout}
                })
                return phonology
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.restrict('GET')
    @h.authenticate_with_JSON
    def servecompiled(self, id):
        """Serve the compiled foma script of the phonology.

        :URL: ``PUT /phonologies/servecompiled/id``
        :param str id: the ``id`` value of a phonology.
        :returns: a stream of bytes -- the compiled phonology script.  

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.foma_installed():
                foma_file_path = get_phonology_file_path(phonology, 'binary')
                if os.path.isfile(foma_file_path):
                    return forward(FileApp(foma_file_path))
                else:
                    response.status_int = 400
                    return json.dumps({'error': 'Phonology %d has not been compiled yet.' % phonology.id})
            else:
                response.status_int = 400
                return json.dumps({'error': 'Foma and flookup are not installed.'})
        else:
            response.status_int = 404
            return json.dumps({'error': 'There is no phonology with id %s' % id})

    @h.jsonify
    @h.restrict('PUT')
    @h.authenticate
    def applydown(self, id):
        """Apply-down (i.e., phonologize) the input in the request body using a phonology.

        :URL: ``PUT /phonologies/applydown/id`` (or ``PUT /phonologies/phonologize/id``)
        :param str id: the ``id`` value of the phonology that will be used.
        :Request body: JSON object of the form ``{'transcriptions': [t1, t2, ...]}``.
        :returns: if the phonology exists and foma is installed, a JSON object
            of the form ``{t1: [p1t1, p2t1, ...], ...}`` where ``t1`` is a
            transcription from the request body and ``p1t1``, ``p2t1``, etc. are
            phonologized outputs of ``t1``.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.foma_installed():
                phonology_binary_path = get_phonology_file_path(phonology, 'binary')
                if os.path.isfile(phonology_binary_path):
                    try:
                        inputs = json.loads(unicode(request.body, request.charset))
                        inputs = MorphophonemicTranscriptionsSchema.to_python(inputs)
                        return phonologize(inputs['transcriptions'], phonology,
                                                 phonology_binary_path, session['user'])
                    except h.JSONDecodeError:
                        response.status_int = 400
                        return h.JSONDecodeErrorResponse
                    except Invalid, e:
                        response.status_int = 400
                        return {'errors': e.unpack_errors()}
                else:
                    response.status_int = 400
                    return {'error': 'Phonology %d has not been compiled yet.' % phonology.id}
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}

    @h.jsonify
    @h.restrict('GET')
    @h.authenticate
    @h.authorize(['administrator', 'contributor'])
    def runtests(self, id):
        """Run the tests defined in the phonology's script against the phonology.

        A line in a phonology's script that begins with "#test" signifies a
        test.  After "#test" there should be a string of characters followed by
        "->" followed by another string of characters.  The first string is the
        underlying representation and the second is the anticipated surface
        representation.  Requests to ``GET /phonologies/runtests/id`` will cause
        the OLD to run a phonology script against its tests and return a
        dictionary detailing the expected and actual outputs of each input in
        the transcription.

        :URL: ``GET /phonologies/runtests/id``
        :param str id: the ``id`` value of the phonology that will be tested.
        :returns: if the phonology exists and foma is installed, a JSON object
            representing the results of the test.

        """
        phonology = Session.query(Phonology).get(id)
        if phonology:
            if h.foma_installed():
                phonology_binary_path = get_phonology_file_path(phonology, 'binary')
                if os.path.isfile(phonology_binary_path):
                    return run_tests(phonology, phonology_binary_path, session['user'])
                else:
                    response.status_int = 400
                    return {'error': 'Phonology %d has not been compiled yet.' % phonology.id}
            else:
                response.status_int = 400
                return {'error': 'Foma and flookup are not installed.'}
        else:
            response.status_int = 404
            return {'error': 'There is no phonology with id %s' % id}


################################################################################
# Backup phonology
################################################################################

def backup_phonology(phonology_dict):
    """Backup a phonology.

    :param dict phonology_dict: a representation of a phonology model.
    :returns: ``None``

    """
    phonology_backup = PhonologyBackup()
    phonology_backup.vivify(phonology_dict)
    Session.add(phonology_backup)


################################################################################
# Phonology Create & Update Functions
################################################################################

def create_new_phonology(data):
    """Create a new phonology.

    :param dict data: the data for the phonology to be created.
    :returns: an SQLAlchemy model object representing the phonology.

    """
    phonology = Phonology()
    phonology.UUID = unicode(uuid4())

    phonology.name = h.normalize(data['name'])
    phonology.description = h.normalize(data['description'])
    phonology.script = h.normalize(data['script'])  # normalize or not?

    phonology.enterer = phonology.modifier = session['user']
    phonology.datetime_modified = phonology.datetime_entered = h.now()
    return phonology

def update_phonology(phonology, data):
    """Update a phonology.

    :param page: the phonology model to be updated.
    :param dict data: representation of the updated phonology.
    :returns: the updated phonology model or, if ``changed`` has not been set
        to ``True``, ``False``.

    """
    changed = False
    # Unicode Data
    changed = h.set_attr(phonology, 'name', h.normalize(data['name']), changed)
    changed = h.set_attr(phonology, 'description', h.normalize(data['description']), changed)
    changed = h.set_attr(phonology, 'script', h.normalize(data['script']), changed)

    if changed:
        session['user'] = Session.merge(session['user'])
        phonology.modifier = session['user']
        phonology.datetime_modified = h.now()
        return phonology
    return changed

def save_phonology_script(phonology):
    """Save the phonology's ``script`` value to disk as ``phonology_<id>.script``.
    
    Also create the phonology compiler shell script, i.e., ``phonology_<id>.sh``
    which will be used to compile the phonology FST to a binary.

    :param phonology: a phonology model.
    :returns: the absolute path to the newly created phonology script file.

    """
    try:
        create_phonology_dir(phonology)
        phonology_script_path = get_phonology_file_path(phonology, 'script')
        phonology_binary_path = get_phonology_file_path(phonology, 'binary')
        phonology_compiler_path = get_phonology_file_path(phonology, 'compiler')
        with codecs.open(phonology_script_path, 'w', 'utf8') as f:
            f.write(phonology.script)
        # The compiler shell script loads the foma script and compiles it to binary form.
        with open(phonology_compiler_path, 'w') as f:
            f.write('#!/bin/sh\nfoma -e "source %s" -e "regex phonology;" -e "save stack %s" -e "quit"' % (
                    phonology_script_path, phonology_binary_path))
        os.chmod(phonology_compiler_path, 0744)
        return phonology_script_path
    except Exception:
        return None

def create_phonology_dir(phonology):
    """Create the directory to hold the phonology script and auxiliary files.
    
    :param phonology: a phonology model object.
    :returns: an absolute path to the directory for the phonology.

    """
    phonology_dir_path = get_phonology_dir_path(phonology)
    h.make_directory_safely(phonology_dir_path)
    return phonology_dir_path

def get_phonology_dir_path(phonology):
    """Return the path to a phonology's directory.
    
    :param phonology: a phonology model object.
    :returns: an absolute path to the directory for the phonology.

    """
    return os.path.join(h.get_OLD_directory_path('phonologies', config=config),
                        'phonology_%d' % phonology.id)

def get_phonology_file_path(phonology, file_type='script'):
    """Return the path to a phonology's file of the given type.
    
    :param phonology: a phonology model object.
    :param str file_type: one of 'script', 'binary', 'compiler', or 'tester'.
    :returns: an absolute path to the phonology's script file.

    """
    ext_map = {'script': 'script', 'binary': 'foma', 'compiler': 'sh', 'tester': 'tester.sh'}
    return os.path.join(get_phonology_dir_path(phonology),
            'phonology_%d.%s' % (phonology.id, ext_map.get(file_type, 'script')))

def remove_phonology_directory(phonology):
    """Remove the directory of the phonology model and everything in it.
    
    :param phonology: a phonology model object.
    :returns: an absolute path to the directory for the phonology.

    """
    try:
        phonology_dir_path = get_phonology_dir_path(phonology)
        rmtree(phonology_dir_path)
        return phonology_dir_path
    except Exception:
        return None

def phonologize(inputs, phonology, phonology_binary_path, user):
    """Phonologize the inputs using the phonology's compiled script.
    
    :param list inputs: a list of morpho-phonemic transcriptions.
    :param phonology: a phonology model.
    :param str phonology_binary_path: an absolute path to a compiled phonology script.
    :param user: a user model.
    :returns: a dictionary: ``{input1: [o1, o2, ...], input2: [...], ...}``

    """
    random_string = h.generate_salt()
    phonology_dir_path = get_phonology_dir_path(phonology)
    inputs_file_path = os.path.join(phonology_dir_path,
            'inputs_%s_%s.txt' % (user.username, random_string))
    outputs_file_path = os.path.join(phonology_dir_path,
            'outputs_%s_%s.txt' % (user.username, random_string))
    applydown_file_path = os.path.join(phonology_dir_path,
            'applydown_%s_%s.sh' % (user.username, random_string))
    with codecs.open(inputs_file_path, 'w', 'utf8') as f:
        inputs = [u'%s%s%s' % (h.word_boundary_symbol, input_, h.word_boundary_symbol)
                  for input_ in inputs]
        f.write(u'\n'.join(inputs))
    with codecs.open(applydown_file_path, 'w', 'utf8') as f:
        f.write('#!/bin/sh\ncat %s | flookup -i %s' % (
                inputs_file_path, phonology_binary_path))
    os.chmod(applydown_file_path, 0744)
    with open(os.devnull, 'w') as devnull:
        with codecs.open(outputs_file_path, 'w', 'utf8') as outfile:
            p = Popen(applydown_file_path, shell=False, stdout=outfile, stderr=devnull)
    p.communicate()
    with codecs.open(outputs_file_path, 'r', 'utf8') as f:
        result = h.foma_output_file2dict(f)
    os.remove(inputs_file_path)
    os.remove(outputs_file_path)
    os.remove(applydown_file_path)
    return result


def get_tests(phonology):
    """Return any tests defined in a phonology's script as a dictionary."""
    result = {}
    test_lines = [l[6:] for l in phonology.script.splitlines() if l[:6] == u'#test ']
    for l in test_lines:
        try:
            i, o = map(unicode.strip, l.split(u'->'))
            result.setdefault(i, []).append(o)
        except ValueError:
            pass
    return result

def run_tests(phonology, phonology_binary_path, user):
    """Run the test defined in the phonology's script and return a report.
    
    :param phonology: a phonology model.
    :param str phonology_binary_path: an absolute path to the phonology's compiled foma script.
    :param user: a user model.
    :returns: a dictionary representing the report on the tests.

    A line in a phonology's script that begins with "#test " signifies a
    test.  After "#test " there should be a string of characters followed by
    "->" followed by another string of characters.  The first string is the
    underlying representation and the second is the anticipated surface
    representation.  Requests to ``GET /phonologies/runtests/id`` will cause
    the OLD to run a phonology script against its tests and return a
    dictionary detailing the expected and actual outputs of each input in the
    transcription.  :func:`run_tests` generates that dictionary.

    """

    tests = get_tests(phonology)
    if not tests:
        response.status_int = 400
        return {'error': 'The script of phonology %d contains no tests.' % phonology.id}
    results = phonologize(tests.keys(), phonology, phonology_binary_path, user)
    return dict([(t, {'expected': tests[t], 'actual': results[t]}) for t in tests])
