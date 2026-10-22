"""Intentional runner outcomes; excluded from test_*.py discovery."""
import unittest


class Outcomes(unittest.TestCase):
    def test_pass(self):
        self.assertTrue(True)

    @unittest.expectedFailure
    def test_expected_failure(self):
        self.fail('Intentional expected failure for reporting.')

    @unittest.skip('Intentional skip for reporting.')
    def test_skip(self):
        pass

    @unittest.expectedFailure
    def test_unexpected_success(self):
        self.assertTrue(True)

    def test_failure(self):
        self.fail('Intentional failure for reporting.')

    def test_error(self):
        raise ValueError('Intentional error for reporting.')
