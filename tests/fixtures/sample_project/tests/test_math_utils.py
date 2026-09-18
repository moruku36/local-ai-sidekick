import unittest

from src.math_utils import factorial


class TestMathUtils(unittest.TestCase):
    def test_factorial_zero(self):
        self.assertEqual(factorial(0), 1)
    def test_factorial_positive(self):
        self.assertEqual(factorial(5), 120)
    def test_factorial_negative(self):
        with self.assertRaises(ValueError):
            factorial(-1)
if __name__ == '__main__':
    unittest.main()
