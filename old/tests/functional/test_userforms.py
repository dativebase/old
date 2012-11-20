from old.tests import *
from nose.tools import nottest

class TestUserformsController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('userforms'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('userforms'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_userform'))

    @nottest
    def test_update(self):
        response = self.app.put(url('userform', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('userform', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('userform', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_userform', id=1))
