from old.tests import *
from nose.tools import nottest

class TestLanguagesController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('languages'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('languages'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_language'))

    @nottest
    def test_update(self):
        response = self.app.put(url('language', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('language', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('language', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_language', id=1))
