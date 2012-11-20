from old.tests import *
from nose.tools import nottest

class TestPagesController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('pages'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('pages'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_page'))

    @nottest
    def test_update(self):
        response = self.app.put(url('page', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('page', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('page', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_page', id=1))
