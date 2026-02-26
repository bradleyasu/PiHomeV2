import configparser
import os


class Configuration:

    def __init__(self, name):
        self.c = configparser.ConfigParser()
        self.name = name
        if not os.path.exists(name):
            self.c.write(open(name, 'w'))
        self.c.read(name)

    def get_int(self, section, key, value):
        value = self.get(section, key, str(value))
        return int(value)

    def get(self, section, key, default):
        if not self.c.has_section(section) or not self.c.has_option(section, key):
            return self.set(section, key, default)
        return self.c[section][key]

    def set(self, section, key, value):
        if not self.c.has_section(section):
            self.c.add_section(section)
        self.c.set(section, key, value)
        self.save()
        return value

    def save(self):
        with open(self.name, 'w') as configfile:  # save
            self.c.write(configfile)

    def reload(self):
        """Re-read the config file into memory. Call after external writes (e.g. Kivy SettingsPanel)."""
        self.c.read(self.name)


CONFIG = Configuration("base.ini")