from old.tests import *
from nose.tools import nottest

class TestUsersController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('users'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('users'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_user'))

    @nottest
    def test_update(self):
        response = self.app.put(url('user', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('user', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('user', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_user', id=1))
