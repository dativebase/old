from old.tests import *
from nose.tools import nottest

class TestFormbackupsController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('formbackups'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('formbackups'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_formbackup'))

    @nottest
    def test_update(self):
        response = self.app.put(url('formbackup', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('formbackup', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('formbackup', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_formbackup', id=1))
