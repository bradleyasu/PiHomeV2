from datetime import datetime
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.clock import Clock
from kivy.animation import Animation


class Countdown(BoxLayout):

    def __init__(self, countdown_time, message, on_timeout, on_phase_change=None, **kwargs):
        super(Countdown, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.dest_time = countdown_time
        self.message = message
        self.on_timeout = on_timeout
        self.on_phase_change = on_phase_change
        self.countdown_event = None
        self.current_phase = None
        self._finished = False

        self.target_year = str(countdown_time.year)

        # --- Normal countdown display ---
        self.normal_box = BoxLayout(orientation='vertical', size_hint=(1, 1))

        # Spacer to push content toward center
        self.normal_box.add_widget(BoxLayout(size_hint=(1, 0.3)))

        # Time units row: 4 groups @ 130px + 3 separators @ 20px = 580px
        self.time_row = BoxLayout(
            orientation='horizontal', size_hint=(None, None),
            width=580, height=140, spacing=0
        )

        self.day_value = self._make_value_label()
        self.day_unit = self._make_unit_label("DAYS")
        self.hr_value = self._make_value_label()
        self.hr_unit = self._make_unit_label("HRS")
        self.min_value = self._make_value_label()
        self.min_unit = self._make_unit_label("MIN")
        self.sec_value = self._make_value_label()
        self.sec_unit = self._make_unit_label("SEC")

        groups = [
            (self.day_value, self.day_unit),
            (self.hr_value, self.hr_unit),
            (self.min_value, self.min_unit),
            (self.sec_value, self.sec_unit),
        ]
        for i, (val_lbl, unit_lbl) in enumerate(groups):
            group = BoxLayout(orientation='vertical', size_hint=(1, 1))
            group.add_widget(val_lbl)
            group.add_widget(unit_lbl)
            self.time_row.add_widget(group)
            if i < 3:
                sep = Label(
                    text=":", font_size='36sp', font_name='Nunito',
                    color=(1, 1, 1, 0.3), size_hint=(None, 1), width=20,
                    valign='top', halign='center'
                )
                sep.text_size = (20, None)
                self.time_row.add_widget(sep)

        # Center the time row
        time_anchor = AnchorLayout(anchor_x='center', anchor_y='center', size_hint=(1, None), height=140)
        time_anchor.add_widget(self.time_row)
        self.normal_box.add_widget(time_anchor)

        # Year label
        self.year_label = Label(
            text=self.target_year, font_size='20sp', font_name='Nunito',
            color=(0.6, 0.5, 1.0, 0.8), size_hint=(1, None), height=40
        )
        self.normal_box.add_widget(self.year_label)

        # Spacer below
        self.normal_box.add_widget(BoxLayout(size_hint=(1, 0.35)))

        self.add_widget(self.normal_box)

        # --- Final countdown display (last 10 seconds) ---
        self.final_box = AnchorLayout(anchor_x='center', anchor_y='center', size_hint=(1, 1))
        self.final_label = Label(
            text='', font_size='120sp', font_name='Nunito',
            color=(1, 1, 1, 1), outline_width=3, outline_color=(0, 0, 0, 0.5),
            bold=True
        )
        self.final_box.add_widget(self.final_label)
        self.final_box.opacity = 0

        # --- Celebration display ---
        self.celebration_box = BoxLayout(orientation='vertical', size_hint=(1, 1))
        self.celebration_box.add_widget(BoxLayout(size_hint=(1, 0.3)))
        self.celebration_label = Label(
            text='', font_size='52sp', font_name='Nunito',
            color=(1, 1, 1, 1), outline_width=3, outline_color=(0, 0, 0, 0.5),
            bold=True
        )
        self.celebration_year = Label(
            text='', font_size='36sp', font_name='Nunito',
            color=(0.6, 0.5, 1.0, 1.0)
        )
        self.celebration_box.add_widget(self.celebration_label)
        self.celebration_box.add_widget(self.celebration_year)
        self.celebration_box.add_widget(BoxLayout(size_hint=(1, 0.35)))
        self.celebration_box.opacity = 0

        # Compute initial values
        self._step()

    def _make_value_label(self):
        lbl = Label(
            text='00', font_size='48sp', font_name='Nunito',
            color=(1, 1, 1, 1), size_hint=(1, 0.75),
            outline_width=2, outline_color=(0, 0, 0, 0.5),
        )
        return lbl

    def _make_unit_label(self, text):
        lbl = Label(
            text=text, font_size='14sp', font_name='Nunito',
            color=(1, 1, 1, 0.4), size_hint=(1, 0.25),
        )
        return lbl

    def _step(self):
        now = datetime.now()
        total = max(0, int((self.dest_time - now).total_seconds()))
        days, remainder = divmod(total, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.days = days
        self.hours = hours
        self.minutes = minutes
        self.seconds = seconds
        self.total_seconds = total

    def _set_phase(self, phase):
        if phase == self.current_phase:
            return
        self.current_phase = phase
        if self.on_phase_change:
            self.on_phase_change(phase)

    def start_countdown(self):
        self.countdown_event = Clock.schedule_interval(self._update, 1)

    def _update(self, dt):
        if self._finished:
            return
        self._step()
        total = self.total_seconds

        if total <= 0:
            self._trigger_celebration()
            return

        # Determine phase and update display
        if total > 3600:
            self._set_phase("ambient")
            self._show_normal()
        elif total > 60:
            self._set_phase("building")
            self._show_normal()
        elif total > 10:
            self._set_phase("building")
            self._show_normal()
            # Pulse the seconds value in the last minute
            if self.sec_value.opacity >= 0.95:
                anim = Animation(opacity=0.5, d=0.4) + Animation(opacity=1.0, d=0.4)
                anim.start(self.sec_value)
        else:
            # Final 10 seconds
            self._set_phase("climax")
            self._show_final(total)

    def _show_normal(self):
        self.day_value.text = str(self.days)
        self.hr_value.text = str(self.hours).zfill(2)
        self.min_value.text = str(self.minutes).zfill(2)
        self.sec_value.text = str(self.seconds).zfill(2)

        # Make sure normal display is visible
        if self.normal_box.opacity < 1:
            Animation.cancel_all(self.normal_box)
            self.normal_box.opacity = 1
        if self.final_box.opacity > 0:
            self.final_box.opacity = 0
            if self.final_box.parent:
                self.remove_widget(self.final_box)

    def _show_final(self, total):
        # Hide normal display, show big countdown number
        if self.normal_box.opacity > 0:
            Animation(opacity=0, d=0.3).start(self.normal_box)

        if not self.final_box.parent:
            self.add_widget(self.final_box)
            Animation(opacity=1, d=0.3).start(self.final_box)

        self.final_label.text = str(total)
        # Scale-up pulse on each tick
        self.final_label.font_size = '130sp'
        anim = Animation(font_size='120sp', d=0.5, t='out_cubic')
        anim.start(self.final_label)

    def _trigger_celebration(self):
        self._finished = True
        self._set_phase("celebration")

        # Hide everything else
        if self.normal_box.parent:
            self.normal_box.opacity = 0
        if self.final_box.parent:
            Animation(opacity=0, d=0.4).start(self.final_box)

        # Show celebration message
        if not self.celebration_box.parent:
            self.add_widget(self.celebration_box)
        self.celebration_label.text = self.message
        self.celebration_year.text = self.target_year
        Animation(opacity=1, d=0.8, t='out_cubic').start(self.celebration_box)

        self.on_timeout()

    def stop_countdown(self):
        if self.countdown_event:
            self.countdown_event.cancel()
            self.countdown_event = None
        Animation.cancel_all(self.sec_value)
        Animation.cancel_all(self.final_label)
        Animation.cancel_all(self.normal_box)
        Animation.cancel_all(self.final_box)
        Animation.cancel_all(self.celebration_box)
