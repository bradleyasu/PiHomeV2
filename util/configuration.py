import configparser
import os
import threading


class Configuration:
    """Thread-safe wrapper around base.ini.

    The config is read/written from several threads (Kivy main thread,
    HTTP server threads via PUT /settings, background services), so every
    access goes through an RLock and saves are atomic (temp file + rename)
    to prevent a torn write from corrupting the file.

    get() never writes to disk: a missing key is filled into the in-memory
    parser (so settings panels still see the default) but only persisted
    when something explicitly calls set()/save().
    """

    def __init__(self, name):
        self._lock = threading.RLock()
        self.c = configparser.ConfigParser()
        self.name = name
        if not os.path.exists(name):
            with open(name, 'w') as f:
                self.c.write(f)
        self.c.read(name)

    def get_int(self, section, key, value):
        raw = self.get(section, key, str(value))
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return int(value)

    def get(self, section, key, default):
        with self._lock:
            if not self.c.has_section(section) or not self.c.has_option(section, key):
                # Record the default in memory only — reads must not
                # trigger disk writes.
                if not self.c.has_section(section):
                    self.c.add_section(section)
                self.c.set(section, key, default)
                return default
            return self.c[section][key]

    def set(self, section, key, value):
        with self._lock:
            if not self.c.has_section(section):
                self.c.add_section(section)
            self.c.set(section, key, value)
            self.save()
            return value

    def save(self):
        with self._lock:
            tmp = self.name + ".tmp"
            with open(tmp, 'w') as configfile:
                self.c.write(configfile)
            os.replace(tmp, self.name)

    def reload(self):
        """Re-read the config file into memory. Call after external writes (e.g. Kivy SettingsPanel)."""
        with self._lock:
            self.c.read(self.name)


CONFIG = Configuration("base.ini")
