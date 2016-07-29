import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import setup_malcolm_paths

from collections import OrderedDict

import unittest
from mock import Mock, patch, call, MagicMock

from malcolm.core.method import Method, takes, returns, only_in, OPTIONAL, \
    REQUIRED
from malcolm.core.meta import Meta
from malcolm.metas.mapmeta import MapMeta
from malcolm.metas.stringmeta import StringMeta
from malcolm.core.serializable import Serializable


class TestMethod(unittest.TestCase):

    def test_init(self):
        m = Method(description="test_description")
        m.set_parent(Mock(), "test_method")
        self.assertEquals("test_method", m.name)
        self.assertEquals("test_description", m.description)
        self.assertEquals("malcolm:core/Method:1.0", m.typeid)
        self.assertEquals(None, m.label)

    def test_set_label(self):
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        m.on_changed = Mock(wrap=m.on_changed)
        m.set_label("new_label")
        self.assertEquals("new_label", m.label)
        m.on_changed.assert_called_once_with([["label"], "new_label"])

    def test_call_calls_call_function(self):
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        call_func_mock = MagicMock()
        call_func_mock.return_value = {"output": 2}
        m.call_function = call_func_mock
        func = Mock(return_value={"first_out": "test"})
        m.set_function(func)
        args_meta = Mock(spec=MapMeta)
        args_meta.elements = {"first": Mock()}
        m.set_takes(args_meta)

        response = m(first="test")

        call_func_mock.assert_called_once_with(dict(first="test"))
        self.assertEqual(response, {"output": 2})

    def test_call_with_positional_args(self):
        func = Mock(return_value={"output": 2})
        m = Method("test_description")
        m.name = "test_method"
        call_func_mock = MagicMock()
        m.call_function = call_func_mock
        m.set_function(func)
        args_meta = Mock(spec=MapMeta)
        validator = Mock(return_value=True)
        args_meta.elements = OrderedDict()
        args_meta.elements["first"] = Mock(validate=validator)
        args_meta.elements["second"] = Mock(validate=validator)
        args_meta.elements["third"] = Mock(validate=validator)
        args_meta.elements["fourth"] = Mock(validate=validator)
        args_meta.required = ["first", "third"]
        m.set_takes(args_meta)

        m(2, 3, third=1, fourth=4)

        call_func_mock.assert_called_once_with({'second': 3, 'fourth': 4,
                                                'third': 1, 'first': 2})

    def test_get_response_calls_call_function(self):
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        call_func_mock = MagicMock()
        m.call_function = call_func_mock
        func = Mock(return_value={"first_out": "test"})
        m.set_function(func)
        args_meta = Mock(spec=MapMeta)
        args_meta.elements = {"first": Mock()}
        m.set_takes(args_meta)
        request = MagicMock()
        request.parameters = dict(first="test")

        m.get_response(request)

        call_func_mock.assert_called_once_with(dict(first="test"))

    def test_get_response_no_parameters(self):
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        call_func_mock = MagicMock()
        m.call_function = call_func_mock
        func = Mock(return_value={"first_out": "test"})
        m.set_function(func)
        args_meta = Mock(spec=MapMeta)
        args_meta.elements = {"first": Mock()}
        m.set_takes(args_meta)
        request = MagicMock()
        del request.parameters  # Make sure mock doesn't have `parameters`

        m.get_response(request)

        call_func_mock.assert_called_once_with(dict())

    def test_get_response_raises(self):
        func = MagicMock()
        func.side_effect = ValueError("Test error")
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        m.set_function(func)
        m.takes = MagicMock()
        m.returns = MagicMock()
        request = MagicMock()

        response = m.get_response(request)
        self.assertEquals("malcolm:core/Error:1.0", response.typeid)
        self.assertEquals(
            "Method test_method raised an error: Test error", response.message)

    def test_simple_function(self):
        func = Mock(return_value={"first_out": "test"})
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        m.set_function(func)
        args_meta = Mock(spec=MapMeta)
        args_meta.elements = dict(first=Mock())
        m.set_takes(args_meta)

    def test_no_args_returns(self):
        func = Mock(return_value={"first_out": "test"})
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        m.set_function(func)
        args_meta = Mock(spec=MapMeta)
        args_meta.elements = dict(first=Mock())
        return_meta = Mock()
        return_meta.elements = {"output1": Mock()}
        m.set_returns(return_meta)

        self.assertEquals({"first_out": "test"}, m.call_function(dict()))

    def test_defaults(self):
        func = Mock(return_value={"first_out": "test"})
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        s = StringMeta(description='desc')
        args_meta = MapMeta()
        args_meta.elements = {"first": s, "second": s}
        m.set_takes(args_meta)
        m.set_defaults({"second": "default"})
        m.set_function(func)

        self.assertEquals({"first_out": "test"}, m.call_function(dict(first="test")))
        call_arg = func.call_args[0][0]
        self.assertEqual("test", call_arg.first)
        self.assertEqual("default", call_arg.second)
        self.assertEqual(args_meta, call_arg.meta)

    def test_required(self):
        func = Mock(return_value={"first_out": "test"})
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        m.set_function(func)
        args_meta = Mock(spec=MapMeta)
        args_meta.elements = {"first": Mock(), "second": Mock()}
        args_meta.required = ["first"]
        m.set_takes(args_meta, {"first": "default"})

        self.assertEquals({"first_out": "test"}, m.call_function({}))
        call_arg = func.call_args[0][0]
        self.assertEqual("default", call_arg.first)
        with self.assertRaises(AttributeError):
            _ = call_arg.second
        self.assertEqual(args_meta, call_arg.meta)

        m.set_takes(args_meta, {"second": "default"})
        with self.assertRaises(ValueError):
            m.call_function({})

    def test_incomplete_return(self):
        func = Mock(return_value={"output1": 2})
        m = Method("test_description")
        m.name = "test_method"
        m.set_function(func)
        s = StringMeta(description='desc')
        args_meta = MapMeta()
        args_meta.elements = {"first": s, "second": s}
        return_meta = MapMeta()
        return_meta.elements = {"output1": s, "output2": s}
        return_meta.validate = Mock(side_effect = \
            KeyError("Return value doesn't match return meta"))
        m.set_takes(args_meta)
        m.set_returns(return_meta)

        with self.assertRaises(KeyError):
            m.call_function(dict(first=1, second=2))
        call_arg1, call_arg2 = func.call_args_list[0][0]
        self.assertEqual('1', call_arg1.first)
        self.assertEqual('2', call_arg1.second)
        self.assertEqual(args_meta, call_arg1.meta)
        self.assertEqual(return_meta, call_arg2.meta)

    @patch('malcolm.core.method.Method.call_function')
    def test_handle_request(self, call_function_mock):
        call_function_mock.return_value = {"output": 1}
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        request = Mock(
                id=(123, Mock()), type="Post", parameters={"first": 2},
                respond_with_return=Mock())

        response = m.get_response(request)

        call_function_mock.assert_called_with({"first": 2})
        self.assertEquals({"output": 1}, response.value)

    def test_not_writeable_stops_call(self):
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        m.set_function(Mock())
        m.set_writeable(False)
        with self.assertRaises(ValueError,
                msg="Cannot call a method that is not writeable"):
            m()

    def test_set_writeable_notifies(self):
        m = Method("test_description")
        m.set_parent(Mock(), "test_method")
        m.on_changed = MagicMock(side_effect=m.on_changed)
        m.set_writeable(False)
        m.on_changed.assert_called_once_with([["writeable"], False])
        m.on_changed.reset_mock()
        m.set_writeable(True)
        m.on_changed.assert_called_once_with([["writeable"], True])

    def test_set_tags_notifies(self):
        m = Method("test_description")
        m.name = "test_method"
        m.on_changed = MagicMock(side_effect=m.on_changed)
        m.set_tags(["new_tag"])
        m.on_changed.assert_called_once_with([["tags"], ["new_tag"]])

    def test_to_dict_serialization(self):
        func = Mock(return_value={"out": "dummy"})
        defaults = {"in_attr": "default"}
        args_meta = Mock(elements={"first": Mock()},
                         to_dict=Mock(
                             return_value=OrderedDict({"dict": "args"})))
        return_meta = Mock(elements={"out": Mock()},
                           to_dict=Mock(
                               return_value=OrderedDict({"dict": "return"})))
        writeable_mock = Mock()
        m = Method("test_description")
        m.name = "test_method"
        m.set_function(func)
        m.set_takes(args_meta, defaults)
        m.set_function_returns(return_meta)
        m.set_writeable(writeable_mock)
        m.set_tags(["tag_1", "tag_2"])
        expected = OrderedDict()
        expected["typeid"] = "malcolm:core/Method:1.0"
        expected["takes"] = OrderedDict({"dict": "args"})
        expected["defaults"] = OrderedDict({"in_attr": "default"})
        expected["description"] = "test_description"
        expected["tags"] = ["tag_1", "tag_2"]
        expected["writeable"] = writeable_mock
        del expected["writeable"].to_dict
        expected["returns"] = OrderedDict({"dict": "return"})
        self.assertEquals(expected, m.to_dict())

    @patch("malcolm.metas.mapmeta.MapMeta.to_dict")
    def test_empty_to_dict_serialization(self, map_to_dict_mock):
        m = Method("test_description")
        m.name = "test_method"
        expected = OrderedDict()
        expected["typeid"] = "malcolm:core/Method:1.0"
        expected["takes"] = map_to_dict_mock.return_value
        del expected['takes'].to_dict
        expected["defaults"] = OrderedDict()
        expected["description"] = "test_description"
        expected["tags"] = []
        expected["writeable"] = True
        expected["returns"] = map_to_dict_mock.return_value
        expected["label"] = None
        self.assertEquals(expected, m.to_dict())

    @patch("malcolm.core.method.MapMeta")
    def test_from_dict_deserialize(self, mock_mapmeta):
        name = "foo"
        description = "dummy description"
        takes = dict(a=object(), b=object(), typeid='malcolm:core/Map:1.0')
        returns = dict(c=object(),typeid='malcolm:core/Map:1.0')
        defaults = dict(a=43, typeid='malcolm:core/Map')
        writeable_mock = Mock()
        tags = ["tag_1"]
        d = dict(description=description, takes=takes,
                 returns=returns, defaults=defaults,
                 writeable=writeable_mock,
                 tags=tags,
                 typeid="malcolm:core/Method:1.0")
        m = Serializable.from_dict(d)
        self.assertEqual(mock_mapmeta.from_dict.call_args_list, [
            call("takes", takes), call("returns", returns)])
        self.assertEqual(m.name, name)
        self.assertEqual(m.takes, mock_mapmeta.from_dict.return_value)
        self.assertEqual(m.returns, mock_mapmeta.from_dict.return_value)
        self.assertEqual(m.defaults, defaults)
        self.assertEquals(m.writeable, writeable_mock)
        self.assertEquals(m.tags, tags)

    @patch("malcolm.core.method.MapMeta")
    def test_takes_given_optional(self, map_meta_mock):
        m1 = MagicMock()
        map_meta_mock.return_value = m1
        a1 = MagicMock()
        a1.name = "name"

        @takes("name", a1, OPTIONAL)
        def say_hello(name):
            """Say hello"""
            print("Hello" + name)

        self.assertTrue(hasattr(say_hello, "Method"))
        self.assertEqual(m1, say_hello.Method.takes)
        m1.add_element.assert_called_once_with(a1, False)
        self.assertEqual(0, len(say_hello.Method.defaults))

    @patch("malcolm.core.method.MapMeta")
    def test_takes_given_defaults(self, map_meta_mock):
        m1 = MagicMock()
        map_meta_mock.return_value = m1
        a1 = MagicMock()
        a1.name = "name"

        @takes(a1, "User", OPTIONAL)
        def say_hello(name):
            """Say hello"""
            print("Hello" + name)

        self.assertTrue(hasattr(say_hello, "Method"))
        self.assertEqual(m1, say_hello.Method.takes)
        m1.add_element.assert_called_once_with(a1, False)
        self.assertEqual("User", say_hello.Method.defaults[a1.name])

    @patch("malcolm.core.method.MapMeta")
    def test_returns_given_valid_sets(self, map_meta_mock):
        m1 = MagicMock()
        map_meta_mock.return_value = m1
        a1 = MagicMock()
        a1.name = "name"

        @returns(a1, REQUIRED)
        def return_hello(name):
            """Return hello"""
            return "Hello" + name

        self.assertTrue(hasattr(return_hello, "Method"))
        self.assertEqual(m1, return_hello.Method.returns)
        m1.add_element.assert_called_once_with(a1, True)

    @patch("malcolm.core.method.MapMeta")
    def test_returns_not_given_req_or_opt_raises(self, _):

        with self.assertRaises(ValueError):
            @returns(MagicMock(), "Raise Error")
            def return_hello(name):
                """Return hello"""
                return "Hello" + name

    def test_only_in(self):
        @only_in("boo", "boo2")
        def f():
            pass

        self.assertTrue(hasattr(f, "Method"))
        self.assertEqual(f.Method.only_in, ("boo", "boo2"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
