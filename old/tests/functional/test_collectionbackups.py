from old.tests import *
from nose.tools import nottest

class TestCollectionbackupsController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('collectionbackups'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('collectionbackups'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_collectionbackup'))

    @nottest
    def test_update(self):
        response = self.app.put(url('collectionbackup', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('collectionbackup', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('collectionbackup', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_collectionbackup', id=1))
