from old.tests import *
from nose.tools import nottest

class TestElicitationmethodsController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('elicitationmethods'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('elicitationmethods'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_elicitationmethod'))

    @nottest
    def test_update(self):
        response = self.app.put(url('elicitationmethod', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('elicitationmethod', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('elicitationmethod', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_elicitationmethod', id=1))
