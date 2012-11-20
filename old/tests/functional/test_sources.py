from old.tests import *
from nose.tools import nottest

class TestSourcesController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('sources'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('sources'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_source'))

    @nottest
    def test_update(self):
        response = self.app.put(url('source', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('source', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('source', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_source', id=1))
