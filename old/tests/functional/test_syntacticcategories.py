from old.tests import *
from nose.tools import nottest

class TestSyntacticcategoriesController(TestController):

    @nottest
    def test_index(self):
        response = self.app.get(url('syntacticcategories'))
        # Test response...

    @nottest
    def test_create(self):
        response = self.app.post(url('syntacticcategories'))

    @nottest
    def test_new(self):
        response = self.app.get(url('new_syntacticcategory'))

    @nottest
    def test_update(self):
        response = self.app.put(url('syntacticcategory', id=1))

    @nottest
    def test_delete(self):
        response = self.app.delete(url('syntacticcategory', id=1))

    @nottest
    def test_show(self):
        response = self.app.get(url('syntacticcategory', id=1))

    @nottest
    def test_edit(self):
        response = self.app.get(url('edit_syntacticcategory', id=1))
