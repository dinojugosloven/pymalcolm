import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
import setup_malcolm_paths

from cothread import catools
from malcolm.parts.ca.cachoicepart import CAChoicePart

import unittest
from mock import Mock, patch, ANY


class TestCAChoicePart(unittest.TestCase):

    def test_init(self):
        catools.caget = Mock(ok=True, enums=['a','b'])
        CAChoicePart.create_attribute = Mock()
        CAChoicePart.rbv = 'Prefix:Suffix_RBV'
        # reading yaml will result in a dictionary such as:-
        d = {"name": "pv",
             "description": "a test pv",
             "pv": "Prefix:Suffix",
             "rbv_suff": "_RBV"}
        p = CAChoicePart("part", Mock(), Mock(), d)

        p.create_attribute.assert_called_once_with(ANY,
                                                   "Prefix:Suffix", rbv=None,
                                                   rbv_suff='_RBV')

        self.assertEqual(p.get_datatype(), catools.DBR_ENUM)

if __name__ == "__main__":
    unittest.main(verbosity=2)