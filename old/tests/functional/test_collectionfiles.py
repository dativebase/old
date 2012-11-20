from old.tests import *
from nose.tools import nottest

class TestCollectionfilesController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('collectionfiles'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('collectionfiles'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_collectionfile'))

    @nottest
    def test_update(self):
        response = self.app.put(url('collectionfile', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('collectionfile', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('collectionfile', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_collectionfile', id=1))
