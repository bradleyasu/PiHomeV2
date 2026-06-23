"""Headless unit tests for util.dependencies (pure-logic helpers).

Run:  python3 -m unittest util.test_dependencies
"""

import unittest

from util import dependencies


class DistNameTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(dependencies._dist_name("requests"), "requests")

    def test_version_pin(self):
        self.assertEqual(dependencies._dist_name("paho-mqtt==1.6.1"), "paho-mqtt")

    def test_range_specifier(self):
        self.assertEqual(dependencies._dist_name("numpy>=1.26,<2"), "numpy")

    def test_extras(self):
        self.assertEqual(dependencies._dist_name("requests[socks]>=2"), "requests")

    def test_environment_marker(self):
        self.assertEqual(
            dependencies._dist_name("zeroconf; python_version >= '3.9'"), "zeroconf"
        )

    def test_whitespace(self):
        self.assertEqual(dependencies._dist_name("  pillow == 10.2.0 "), "pillow")


class MissingTests(unittest.TestCase):
    def test_installed_package_not_missing(self):
        # 'pip' is a real distribution and is present in any env that can run
        # these tests (the module shells out to `python -m pip`).
        self.assertNotIn("pip", dependencies._missing(["pip"]))

    def test_absent_package_reported(self):
        self.assertEqual(
            dependencies._missing(["this-package-does-not-exist-xyz123"]),
            ["this-package-does-not-exist-xyz123"],
        )

    def test_option_injection_rejected(self):
        self.assertEqual(dependencies._missing(["--upgrade-strategy=eager"]), [])
        self.assertEqual(dependencies._missing(["-rrequirements.txt"]), [])

    def test_blank_entries_ignored(self):
        self.assertEqual(dependencies._missing(["", "  ", None]), [])


if __name__ == "__main__":
    unittest.main()
