import sys
import os
import unittest
from collections import OrderedDict
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import setup_malcolm_paths

from malcolm.metas import ChoiceMeta
from malcolm.core.serializable import Serializable


class TestInit(unittest.TestCase):

    def setUp(self):
        self.choice_meta = ChoiceMeta(
            "TestMeta", "test description", [1, 2, 3])

    def test_values_after_init(self):
        self.assertEqual("TestMeta", self.choice_meta.name)
        self.assertEqual(
            "test description", self.choice_meta.description)
        self.assertEqual(
            self.choice_meta.typeid, "malcolm:core/ChoiceMeta:1.0")
        self.assertEqual(
            self.choice_meta.label, "TestMeta")


class TestValidate(unittest.TestCase):

    def setUp(self):
        self.choice_meta = ChoiceMeta(
            "TestMeta", "test description", [1, 2, 3])

    def test_given_valid_value_then_return(self):
        response = self.choice_meta.validate(1)
        self.assertEqual(1, response)

    def test_None_valid(self):
        response = self.choice_meta.validate(None)
        self.assertEqual(None, response)

    def test_given_invalid_value_then_raises(self):
        with self.assertRaises(ValueError):
            self.choice_meta.validate(0)

    def test_set_choices(self):
        self.choice_meta.set_choices([4, 5, 6])

        self.assertEqual([4, 5, 6], self.choice_meta.choices)


class TestSerialisation(unittest.TestCase):

    def setUp(self):
        self.choice_meta = ChoiceMeta("Test", "test description", [1, 2, 3])

    def test_to_dict(self):
        expected_dict = OrderedDict()
        expected_dict["typeid"] = "malcolm:core/ChoiceMeta:1.0"
        expected_dict["choices"] = [1, 2, 3]
        expected_dict["description"] = "test description"
        expected_dict["tags"] = []
        expected_dict["writeable"] = True
        expected_dict["label"] = "Test"

        response = self.choice_meta.to_dict()

        self.assertEqual(expected_dict, response)

    def test_from_dict(self):
        d = dict(description="test description",
                 choices=[1, 2, 3],
                 tags=["tag"],
                 writeable=False,
                 label="label")
        s = ChoiceMeta.from_dict("me", d)
        self.assertEqual(type(s), ChoiceMeta)
        self.assertEqual(s.name, "me")
        self.assertEqual(s.choices, [1, 2, 3])
        self.assertEqual(s.tags, ["tag"])
        self.assertFalse(s.writeable)
        self.assertEqual(s.label, "label")

if __name__ == "__main__":
    unittest.main(verbosity=2)