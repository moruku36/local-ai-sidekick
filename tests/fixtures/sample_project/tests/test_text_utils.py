import unittest
from src.text_utils import reverse_string
class TestTextUtils(unittest.TestCase):
    def test_reverse_string(self):
        self.assertEqual(reverse_string('hello'), 'olleh')
        self.assertEqual(reverse_string(''), '')
        self.assertEqual(reverse_string('a'), 'a')
if __name__ == '__main__':
    unittest.main()