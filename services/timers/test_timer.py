import unittest
from services.timers.timer import Timer

class TestTimer(unittest.TestCase):
    def test_timer(self):
        test_timer = Timer(duration=5)
        test_timer.start()
        while test_timer.is_running is True:
            pass
        test_timer.stop()
        self.assertEqual(test_timer.get_elapsed_time(), 5.0)

    
    def test_timer_with_listeners(self):
        test_timer = Timer(duration=5)
        self.listener_called = False
        def set_listener_called(time):
            self.assertEqual(time, 5.0)
            self.listener_called = True
        test_timer.add_listener(lambda t: set_listener_called(t))
        test_timer.start()
        while test_timer.is_running is True:
            pass
        test_timer.stop()
        self.assertEqual(self.listener_called, True)

