from old.tests import *
from nose.tools import nottest

class TestOldcollectionsController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('oldcollections'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('oldcollections'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_collection'))

    @nottest
    def test_update(self):
        response = self.app.put(url('collection', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('collection', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('collection', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_collection', id=1))
