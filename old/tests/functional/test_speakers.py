from old.tests import *
from nose.tools import nottest

class TestSpeakersController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('speakers'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('speakers'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_speaker'))

    @nottest
    def test_update(self):
        response = self.app.put(url('speaker', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('speaker', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('speaker', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_speaker', id=1))
