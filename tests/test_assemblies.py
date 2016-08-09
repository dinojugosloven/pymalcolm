import os
import sys
sys.path.append(os.path.dirname(__file__))
import setup_malcolm_paths

import unittest
from mock import Mock, patch

from malcolm.core import method_takes, REQUIRED, Block
from malcolm.core.vmetas import StringMeta
from malcolm.assemblyutil import make_assembly, split_into_sections, \
    with_takes_from, substitute_params, make_block_instance, call_with_map


class TestAssemblies(unittest.TestCase):

    @patch("malcolm.assemblyutil.make_block_instance")
    def test_make_assembly(self, mock_make):
        yaml = """
parameters.string:
    name: something
    description: my description

parts.ca.CADoublePart:
    pv: $(something)
"""
        collection = make_assembly(yaml)
        process = Mock()
        blocks = collection(process, dict(name="boo", something="mypv"))
        mock_make.assert_called_once_with(
            "boo", process, {}, {"ca.CADoublePart": {"pv": "mypv"}})
        self.assertEqual(blocks, [mock_make.return_value])

    def test_split_into_sections(self):
        ds = {"parameters.string": {"name": "something"},
              "controllers.ManagerController": None}
        expected = dict(
            parameters={"string": {"name": "something"}},
            controllers={"ManagerController": None},
            parts={},
            assemblies={})
        self.assertEqual(split_into_sections(ds), expected)

    def test_with_takes_from(self):
        parameters = {"string": {"name": "something", "description": ""}}
        @with_takes_from(parameters, include_name=True)
        def f():
            pass
        elements = f.MethodMeta.takes.elements
        self.assertEquals(len(elements), 2)
        self.assertEquals(list(elements), ["name", "something"])


    def test_with_takes_from_no_name(self):
        parameters = {"string": {"name": "something", "description": ""}}
        @with_takes_from(parameters, include_name=False)
        def f():
            pass
        elements = f.MethodMeta.takes.elements
        self.assertEquals(len(elements), 1)
        self.assertEquals(list(elements), ["something"])

    def test_substitute_params(self):
        d = {"name": "$(name):pos", "exposure": 1.0}
        params = {"name": "me"}
        substitute_params(d, params)
        expected = {"name": "me:pos", "exposure": 1.0}
        self.assertEqual(d, expected)

    def test_make_block_instance(self):
        # TODO: needs new controller and part stuff
        pass

        parts_d = {"ca.CADoublePart": {
            "name": "me", "description": "my pv desc", "pv": "MY:PV:STRING"}}
        controllers_d = {}
        name = "block_name"
        process = Mock()
        inst = make_block_instance(name, process, controllers_d, parts_d)
        self.assertIsInstance(inst, Block)
        process.add_block.assert_called_once_with(inst)
        self.assertEqual(inst.path_relative_to(process), [name])

    def test_call_with_map(self):
        @method_takes(
            "desc", StringMeta("description"), REQUIRED,
            "foo", StringMeta("optional thing"), "thing"
        )
        def f(extra, params):
            return extra, 2, params.desc, params.foo

        ca = Mock(CAPart=f)
        parts = Mock(ca=ca)

        result = call_with_map(parts, "ca.CAPart", dict(desc="my name"), "extra")
        self.assertEqual(result, ("extra", 2, "my name", "thing"))

    def test_all_yamls(self):
        from malcolm.assemblies.demo import hello
        process = Mock()
        blocks = hello(process, dict(name="boo"))
        self.assertEqual(len(blocks), 1)
        process.add_block.assert_called_once_with(blocks[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)