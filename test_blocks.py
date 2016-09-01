import unittest
from io import StringIO
from contextlib import redirect_stdout
from cli.blocks import Command, Commandlet, Mode, ArgumentParser




class TestMode(unittest.TestCase):
    def setUp(self):
        self.mode = Mode()

    def tearDown(self):
        del self.mode

    def test_get_user_input(self):
        out = StringIO()
        with redirect_stdout(out):
            with self.subTest('default name and context'):
                self.mode.get_user_input()
                self.assertEqual(out.getvalue(), 'unnamed: ')

            with self.subTest('custom name and context'):
                self.mode.get_user_input()
                self.mode.name = 'name'
                self.mode.context = 'context'
                self.assertEqual(self.out.getvalue().strip(), 'name(context): ')


class TestArgumentParser(unittest.TestCase):
    def setUp(self):
        self.parser = ArgumentParser()

    def tearDown(self):
        del self.parser

    def test_call__(self):
        test_input = ' test "" "with space"   \'with "space and different" quote\' case '
        known_output = ('test', '', 'with space', 'with "space and different" quote', 'case')

        test_output = self.parser(test_input)
        self.assertTupleEqual(known_output, test_output, test_output)


if __name__ == '__main__':
    unittest.main()
