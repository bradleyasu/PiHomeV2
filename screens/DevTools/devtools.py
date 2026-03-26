import subprocess

from kivy.lang import Builder
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (
    ColorProperty,
    StringProperty,
    NumericProperty,
    BooleanProperty,
)

from components.Button.simplebutton import SimpleButton
from components.Msgbox.msgbox import MSGBOX_FACTORY, MSGBOX_BUTTONS
from interface.pihomescreen import PiHomeScreen
from interface.pihomescreenmanager import PIHOME_SCREEN_MANAGER
from screens.DevTools.sysinfo import (
    get_cpu_temp,
    get_memory_usage,
    get_disk_usage,
    get_uptime,
    get_hostname,
    get_python_version,
    get_os_info,
    get_architecture,
    get_local_ip,
)
from server.server import SERVER
from services.qr.qr import QR
from services.taskmanager.taskmanager import TASK_MANAGER
from system.brightness import get_brightness, set_brightness
from theme.theme import Theme
from util.configuration import CONFIG
from util.const import SERVER_PORT
from util.helpers import get_app
from util.phlog import PIHOME_LOGGER

Builder.load_file("./screens/DevTools/devtools.kv")


class DevTools(PiHomeScreen):
    theme = Theme()

    # Theme colors (defaults overridden by on_config_update)
    bg_color     = ColorProperty([0.04, 0.04, 0.06, 1])
    header_color = ColorProperty([0.07, 0.07, 0.10, 1])
    card_color   = ColorProperty([0.09, 0.09, 0.13, 1])
    text_color   = ColorProperty([1, 1, 1, 1])
    muted_color  = ColorProperty([1, 1, 1, 0.45])
    accent_color = ColorProperty([0.3, 0.7, 1.0, 1])
    status_color = ColorProperty([0.45, 0.45, 0.45, 1])

    # System metrics
    cpu_temp = StringProperty("--")
    mem_text = StringProperty("-- / -- MB")
    mem_percent = NumericProperty(0)
    disk_text = StringProperty("-- / -- GB")
    disk_percent = NumericProperty(0)
    uptime_text = StringProperty("--")
    hostname = StringProperty("--")
    local_ip = StringProperty("0.0.0.0")
    os_info = StringProperty("--")
    arch_info = StringProperty("--")
    python_ver = StringProperty("--")

    # Server info
    server_url = StringProperty("--")
    ws_url = StringProperty("--")
    server_status = StringProperty("Offline")
    server_online = BooleanProperty(False)

    # Screen info
    screen_count = StringProperty("0")
    current_screen_name = StringProperty("--")

    # Brightness
    brightness_val = NumericProperty(50)

    # Log level
    log_level = StringProperty("INFO")

    # QR code
    qr_source = StringProperty("")

    _poll_event = None
    _buttons_built = False

    def __init__(self, **kwargs):
        super(DevTools, self).__init__(**kwargs)
        self.disable_rotary_press_animation = True

    def on_enter(self, *args):
        super().on_enter(*args)
        if not self._buttons_built:
            Clock.schedule_once(lambda dt: self._build_action_buttons(), 0)
        self._refresh_static()
        self._refresh_metrics()
        self._generate_qr()
        self._poll_event = Clock.schedule_interval(lambda dt: self._refresh_metrics(), 3.0)

    def _build_action_buttons(self):
        panel = self.ids.get("actions_panel")
        if not panel:
            return

        buttons = [
            ("Restart PiHome",   "primary",   self.action_restart_pihome),
            ("Update PiHome",    "secondary",  self.action_update_pihome),
            ("Reboot System",    "danger",    self.action_restart_os),
            ("Shutdown",         "danger",    self.action_shutdown),
            ("Toggle Theme",     "secondary", self.action_toggle_theme),
            ("Toggle Server",    "secondary", self.action_toggle_server),
            ("Reload Config",    "secondary", self.action_reload_config),
            ("Clear Task Cache", "secondary", self.action_clear_task_cache),
            ("Test Toast",       "secondary", self.action_test_toast),
            ("Install Splash",   "secondary", self.action_install_splash),
        ]

        pad = dp(8)
        top_offset = dp(26)
        spacing = dp(6)
        cols = 2
        btn_h = dp(36)
        panel_w = panel.width

        col_w = (panel_w - pad * 2 - spacing * (cols - 1)) / cols

        for i, (label, btn_type, callback) in enumerate(buttons):
            row = i // cols
            col = i % cols
            x = panel.x + pad + col * (col_w + spacing)
            y = panel.top - top_offset - (row + 1) * (btn_h + spacing)

            btn = SimpleButton(text=label, type=btn_type, size=(col_w, btn_h))
            btn.pos = (x, y)
            btn.bind(on_release=lambda _, cb=callback: cb())
            panel.add_widget(btn)

        self._buttons_built = True

    def on_pre_leave(self, *args):
        if self._poll_event:
            self._poll_event.cancel()
            self._poll_event = None
        super().on_pre_leave(*args)

    def on_rotary_turn(self, direction, button_pressed):
        new_val = max(5, min(100, self.brightness_val + (direction * 5)))
        self.brightness_val = new_val
        set_brightness(new_val)
        return True

    def on_rotary_pressed(self):
        self.go_back()
        return True

    def on_rotary_long_pressed(self):
        self.go_back()
        return True

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------
    def _refresh_static(self):
        self.hostname = get_hostname()
        self.local_ip = get_local_ip()
        self.os_info = get_os_info()
        self.arch_info = get_architecture()
        self.python_ver = get_python_version()
        self.log_level = CONFIG.get("logging", "level", "INFO").upper()
        self.brightness_val = get_brightness()

        self.server_url = "http://{}:{}".format(self.local_ip, SERVER_PORT)
        self.ws_url = "ws://{}:8765".format(self.local_ip)

    def _refresh_metrics(self):
        self.cpu_temp = get_cpu_temp()

        mem = get_memory_usage()
        self.mem_text = "{} / {} MB".format(mem["used_mb"], mem["total_mb"])
        self.mem_percent = mem["percent"]

        disk = get_disk_usage()
        self.disk_text = "{} / {} GB".format(disk["used_gb"], disk["total_gb"])
        self.disk_percent = disk["percent"]

        self.uptime_text = get_uptime()

        self.server_online = SERVER.is_online()
        self.server_status = "Online" if self.server_online else "Offline"

        loaded = getattr(PIHOME_SCREEN_MANAGER, "loaded_screens", {})
        self.screen_count = str(len(loaded))
        current = getattr(PIHOME_SCREEN_MANAGER, "current", "")
        self.current_screen_name = current if current else "--"

    def _generate_qr(self):
        try:
            path = QR().from_url(
                "http://{}:{}".format(self.local_ip, SERVER_PORT),
                filename="devtools_qr.png",
            )
            self.qr_source = path
        except Exception as e:
            PIHOME_LOGGER.error("DevTools: QR generation failed: {}".format(e))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_restart_pihome(self):
        def do_restart():
            PIHOME_LOGGER.info("DevTools: Restarting PiHome service...")
            PIHOME_SCREEN_MANAGER.goto("_shutdown")
        MSGBOX_FACTORY.show(
            "Restart PiHome",
            "Restart the PiHome application?",
            0, 1, MSGBOX_BUTTONS["YES_NO"],
            on_yes=lambda: do_restart(),
        )

    def action_restart_os(self):
        def do_reboot():
            PIHOME_LOGGER.info("DevTools: Rebooting system...")
            try:
                subprocess.Popen(
                    ["sudo", "reboot"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                PIHOME_LOGGER.error("DevTools: Reboot failed: {}".format(e))

        MSGBOX_FACTORY.show(
            "Reboot System",
            "Reboot the Raspberry Pi? PiHome will restart automatically.",
            0, 1, MSGBOX_BUTTONS["YES_NO"],
            on_yes=lambda: do_reboot(),
        )

    def action_shutdown(self):
        PIHOME_SCREEN_MANAGER.goto("_shutdown")

    def action_clear_task_cache(self):
        def do_clear():
            TASK_MANAGER.delete_task_cache()
            PIHOME_LOGGER.info("DevTools: Task cache cleared")

        MSGBOX_FACTORY.show(
            "Clear Task Cache",
            "Delete all cached tasks? This cannot be undone.",
            0, 1, MSGBOX_BUTTONS["YES_NO"],
            on_yes=lambda: do_clear(),
        )

    def action_reload_config(self):
        CONFIG.reload()
        PIHOME_SCREEN_MANAGER.reload_all()
        self._refresh_static()
        PIHOME_LOGGER.info("DevTools: Configuration reloaded")

    def action_toggle_theme(self):
        current = CONFIG.get("theme", "dark_mode", "1")
        new_val = "0" if current == "1" else "1"
        CONFIG.set("theme", "dark_mode", new_val)
        PIHOME_SCREEN_MANAGER.reload_all()
        self._refresh_static()

    def action_toggle_server(self):
        if SERVER.is_online():
            SERVER.stop_server()
        else:
            SERVER.start_server()
        Clock.schedule_once(lambda dt: self._refresh_metrics(), 0.5)

    def action_update_pihome(self):
        def do_update():
            PIHOME_LOGGER.info("DevTools: Pulling latest from git...")
            try:
                result = subprocess.run(
                    ["git", "-C", "/usr/local/PiHome", "pull", "--ff-only"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
                output = result.stdout.decode("utf-8", errors="replace").strip()
                PIHOME_LOGGER.info("DevTools: Git pull result: {}".format(output))
                Clock.schedule_once(
                    lambda dt: MSGBOX_FACTORY.show(
                        "Update Complete",
                        output if output else "Up to date",
                        10, 2, 0,
                    ),
                    0,
                )
            except Exception as e:
                PIHOME_LOGGER.error("DevTools: Update failed: {}".format(e))
                Clock.schedule_once(
                    lambda dt: MSGBOX_FACTORY.show(
                        "Update Failed", str(e), 10, 0, 0
                    ),
                    0,
                )

        MSGBOX_FACTORY.show(
            "Update PiHome",
            "Pull the latest version from git?",
            0, 2, MSGBOX_BUTTONS["YES_NO"],
            on_yes=lambda: do_update(),
        )

    def action_test_toast(self):
        get_app().show_toast("Hello world", level="info", timeout=5)

    def action_install_splash(self):
        import threading

        def do_install():
            PIHOME_LOGGER.info("DevTools: Installing boot splash...")
            pihome_dir = "/usr/local/PiHome"
            errors = []

            # 1. Install fbi
            try:
                subprocess.run(
                    ["sudo", "apt-get", "-y", "install", "fbi"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
                )
            except Exception as e:
                errors.append("fbi install: {}".format(e))

            # 2. Install splash service
            try:
                subprocess.run(
                    ["sudo", "cp",
                     "{}/setup/pihome-splash.service".format(pihome_dir),
                     "/etc/systemd/system/"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                )
                subprocess.run(
                    ["sudo", "systemctl", "daemon-reload"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                )
                subprocess.run(
                    ["sudo", "systemctl", "enable", "pihome-splash.service"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                )
            except Exception as e:
                errors.append("splash service: {}".format(e))

            # 3. Update PiHome service (adds splash kill before start)
            try:
                subprocess.run(
                    ["sudo", "cp",
                     "{}/setup/pihome.service".format(pihome_dir),
                     "/etc/systemd/system/"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                )
                subprocess.run(
                    ["sudo", "systemctl", "daemon-reload"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                )
            except Exception as e:
                errors.append("pihome service: {}".format(e))

            # 4. Quiet boot console
            try:
                cmdline = "/boot/cmdline.txt"
                import os
                if not os.path.isfile(cmdline) and os.path.isfile("/boot/firmware/cmdline.txt"):
                    cmdline = "/boot/firmware/cmdline.txt"

                if os.path.isfile(cmdline):
                    with open(cmdline, "r") as f:
                        current = f.read().strip()

                    quiet_opts = ["quiet", "splash", "loglevel=0", "logo.nologo",
                                  "vt.global_cursor_default=0", "consoleblank=0"]
                    for opt in quiet_opts:
                        if opt not in current:
                            current += " " + opt

                    subprocess.run(
                        ["sudo", "bash", "-c",
                         "cp {0} {0}.bak && echo '{1}' > {0}".format(cmdline, current)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                    )
            except Exception as e:
                errors.append("cmdline.txt: {}".format(e))

            # 5. Disable rainbow splash
            try:
                config = "/boot/config.txt"
                import os
                if not os.path.isfile(config) and os.path.isfile("/boot/firmware/config.txt"):
                    config = "/boot/firmware/config.txt"

                if os.path.isfile(config):
                    with open(config, "r") as f:
                        contents = f.read()
                    if "disable_splash=1" not in contents:
                        subprocess.run(
                            ["sudo", "bash", "-c",
                             "echo 'disable_splash=1' >> {}".format(config)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                        )
            except Exception as e:
                errors.append("config.txt: {}".format(e))

            if errors:
                msg = "Completed with errors:\n" + "\n".join(errors)
                PIHOME_LOGGER.error("DevTools: Splash install errors: {}".format(errors))
            else:
                msg = "Boot splash installed. Reboot to see it."
                PIHOME_LOGGER.info("DevTools: Boot splash installed successfully")

            Clock.schedule_once(
                lambda dt: MSGBOX_FACTORY.show("Install Splash", msg, 10, 2, 0), 0
            )

        def run_install():
            thread = threading.Thread(target=do_install, daemon=True, name="splash-install")
            thread.start()

        MSGBOX_FACTORY.show(
            "Install Boot Splash",
            "Install the boot splash screen, quiet the boot console, and update the PiHome service? A reboot will be required.",
            0, 1, MSGBOX_BUTTONS["YES_NO"],
            on_yes=lambda: run_install(),
        )

    def on_config_update(self, config):
        self.log_level = CONFIG.get("logging", "level", "INFO").upper()
        super().on_config_update(config)
