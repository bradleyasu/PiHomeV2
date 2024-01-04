import unittest
from arrowbutton import ArrowButton, HORIZONTAL, VERTICAL, LEFT, RIGHT, UP, DOWN

class TestArrowButton(unittest.TestCase):
    def setUp(self):
        self.arrow_button = ArrowButton()

    def test_initial_values(self):
        self.assertEqual(self.arrow_button.orientation, HORIZONTAL)
        self.assertEqual(self.arrow_button.direction, LEFT)
        self.assertEqual(self.arrow_button.color, [1,1,1,1])
        self.assertEqual(self.arrow_button.points, [])

    def test_calculate_points(self):
        self.arrow_button.calculate_points()
        self.assertNotEqual(self.arrow_button.points, [])
        width = self.arrow_button.width
        self.assertEqual(self.arrow_button.points, [width / 2, width, width, width / 2, width / 2, 0])

    def test_on_touch_down(self):
        self.arrow_button.on_touch_down(touch=MockTouch(10, 10))
        self.assertEqual(self.arrow_button.direction, RIGHT)

        self.arrow_button.orientation = VERTICAL
        self.arrow_button.direction = UP
        self.arrow_button.on_touch_down(touch=MockTouch(10, 10))
        self.assertEqual(self.arrow_button.direction, DOWN)

class MockTouch:
    def __init__(self, x, y):
        self.pos = (x, y)

if __name__ == '__main__':
    unittest.main()