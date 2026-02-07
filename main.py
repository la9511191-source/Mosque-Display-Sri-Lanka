import tkinter as tk
from datetime import datetime, timedelta
from hijridate import Gregorian
from PIL import Image, ImageTk
import os
import json
import re
import requests

# ================= SETTINGS =================
MASJID_NAME = "Porwai Muhiyaddeen \n Jumma Masjid"
SETTINGS_FILE = "settings.txt"
CITY = "Matara"
COUNTRY = "Sri Lanka"
METHOD = 1

COLORS = [
    "gold", "cyan", "#00FF00", "white", "#00CCFF", "red", "#FFBF00", "magenta",
    "#FF5733", "#33FFBD", "#A033FF", "#FF3385", "#33FFF5", "#F3FF33", "#99FF99",
    "#FF8C00", "#00CED1", "#FF1493", "#ADFF2F", "#00BFFF"
]

BG_COLORS = ["black", "#110000", "#001100", "#000011", "#111100", "#1a1a1a", "#002222", "#220022", "#1e1e2e", "#0a0e14"]

DEFAULT_PRAYER_DATA = {
    "Fajr": {"time": [5, 13], "iqamath": 15},
    "Sunrise": {"time": [6, 25], "iqamath": 0},
    "Dhuhr": {"time": [12, 22], "iqamath": 15, "jumuah_iqamath": 45},
    "Asr": {"time": [15, 43], "iqamath": 15},
    "Maghrib": {"time": [18, 18], "iqamath": 10},
    "Isha": {"time": [19, 30], "iqamath": 15}
}
PRAYER_ORDER = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "images.png")


class MosqueDisplay:
    def __init__(self, root):
        self.root = root
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="black")
        self.root.bind("<Escape>", self.on_escape)
        self.root.config(cursor="none")

        self.prayer_data = DEFAULT_PRAYER_DATA.copy()
        self.raw_announcements = ";; Welcome to Mosque,, Please silent your phones"
        self.c_idx_masjid = 0
        self.c_idx_clock = 1
        self.c_idx_prayer = 2
        self.c_idx_prayer_high = 0
        self.c_idx_greg_cal = 3
        self.c_idx_hijri_cal = 0
        self.c_idx_iqamath_text = 3
        self.c_idx_iqamath_bg = 0

        self.ticker_items = []
        self.ticker_pos = self.root.winfo_screenwidth()

        # Track the current day to trigger auto-updates at midnight
        self.current_day = datetime.now().day

        self.load_settings_from_file()
        self.fetch_prayer_times()

        self.iqamath_active = False
        self.alert_active = False
        self.triggering_azan = ""
        self.preview_mode = False
        self.selected_prayer = None
        self.flash_state = True
        self.last_interaction_time = datetime.now()

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        self.canvas = tk.Canvas(root, width=self.screen_w, height=self.screen_h, highlightthickness=0, bg="black")
        self.canvas.pack()

        self.load_background()
        self.setup_ui()
        self.root.bind("<Key>", self.handle_keys)

        self.root.bind("<F1>", lambda e: self.cycle_element("masjid"))
        self.root.bind("<F2>", lambda e: self.cycle_element("clock"))
        self.root.bind("<F3>", lambda e: self.cycle_element("prayer"))
        self.root.bind("<F9>", lambda e: self.cycle_element("prayer_high"))
        self.root.bind("<F7>", lambda e: self.cycle_element("greg_cal"))
        self.root.bind("<F8>", lambda e: self.cycle_element("hijri_cal"))
        self.root.bind("<F5>", lambda e: self.cycle_element("count_txt"))
        self.root.bind("<F6>", lambda e: self.cycle_element("count_bg"))

        self.update_clock()
        self.scroll_ticker()

    def load_background(self):
        if os.path.exists(IMAGE_PATH):
            try:
                img = Image.open(IMAGE_PATH).resize((self.screen_w, self.screen_h), Image.Resampling.LANCZOS)
                self.bg_photo = ImageTk.PhotoImage(img)
                self.bg_img_id = self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
            except:
                self.bg_img_id = self.canvas.create_rectangle(0, 0, self.screen_w, self.screen_h, fill="black")
        else:
            self.bg_img_id = self.canvas.create_rectangle(0, 0, self.screen_w, self.screen_h, fill="black")

    def fetch_prayer_times(self):
        """Fetches data from Aladhan API for Matara."""
        try:
            url = f"http://api.aladhan.com/v1/timingsByCity?city={CITY}&country={COUNTRY}&method={METHOD}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()['data']['timings']
                mapping = {"Fajr": "Fajr", "Sunrise": "Sunrise", "Dhuhr": "Dhuhr", "Asr": "Asr", "Maghrib": "Maghrib",
                           "Isha": "Isha"}
                for api_key, our_key in mapping.items():
                    h, m = map(int, data[api_key].split(':'))
                    self.prayer_data[our_key]["time"] = [h, m]

                self.save_settings_to_file()
                print(f"Prayer times auto-updated for {CITY}: {datetime.now()}")
        except:
            print("Auto-update failed: Check internet connection.")

    def hex_to_rgb(self, h):
        if h.startswith('#'): return tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
        names = {"gold": (255, 215, 0), "cyan": (0, 255, 255), "red": (255, 0, 0), "white": (255, 255, 255)}
        return names.get(h.lower(), (255, 255, 255))

    def rgb_to_hex(self, rgb):
        return '#%02x%02x%02x' % rgb

    def fade_prayer_text(self, prayer_key, target_color, steps=10, current_step=0):
        if prayer_key not in self.prayer_objs: return
        obj = self.prayer_objs[prayer_key]
        current_fill = self.canvas.itemcget(obj["main"], "fill")
        start_rgb = self.hex_to_rgb(current_fill)
        end_rgb = self.hex_to_rgb(target_color)
        if current_step <= steps:
            new_rgb = tuple(int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * (current_step / steps)) for i in range(3))
            self.update_shadow_text(obj, new_color=self.rgb_to_hex(new_rgb))
            self.root.after(30, lambda: self.fade_prayer_text(prayer_key, target_color, steps, current_step + 1))

    def create_shadow_text(self, x, y, text, font, color, anchor="center", justify="center"):
        shadows = []
        for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
            s = self.canvas.create_text(x + dx, y + dy, text=text, font=font, fill="black", anchor=anchor,
                                        justify=justify)
            shadows.append(s)
        main = self.canvas.create_text(x, y, text=text, font=font, fill=color, anchor=anchor, justify=justify)
        return {"main": main, "shadows": shadows}

    def update_shadow_text(self, text_dict, new_text=None, new_color=None):
        if new_text is not None:
            self.canvas.itemconfig(text_dict["main"], text=new_text)
            for s in text_dict["shadows"]: self.canvas.itemconfig(s, text=new_text)
        if new_color is not None:
            self.canvas.itemconfig(text_dict["main"], fill=new_color)

    def setup_ui(self):
        Y_PRAYER = self.screen_h * 0.75
        self.full_screen_overlay = self.canvas.create_rectangle(0, 0, self.screen_w, self.screen_h - 120, fill="black",
                                                                stipple="gray50", outline="")
        self.title_obj = self.create_shadow_text(self.screen_w // 2, 110, MASJID_NAME, ("Arial", 85, "bold"),
                                                 COLORS[self.c_idx_masjid])
        self.clock_obj = self.create_shadow_text(self.screen_w // 2, self.screen_h * 0.46, "", ("Arial", 140, "bold"),
                                                 COLORS[self.c_idx_clock])
        self.date_obj = self.create_shadow_text(self.screen_w // 2, self.screen_h * 0.32, "", ("Arial", 45, "bold"),
                                                COLORS[self.c_idx_greg_cal])
        self.hijri_obj = self.create_shadow_text(self.screen_w // 2, self.screen_h * 0.60, "", ("Arial", 45, "bold"),
                                                 COLORS[self.c_idx_hijri_cal])

        self.ticker_y = self.screen_h - 70
        self.ticker_bg = self.canvas.create_rectangle(0, self.screen_h - 120, self.screen_w, self.screen_h - 20,
                                                      fill="#1a1a1a", outline="")
        self.create_rich_ticker()

        self.mode_header = self.create_shadow_text(self.screen_w * 0.03, Y_PRAYER + 30, "", ("Arial", 42, "bold"),
                                                   COLORS[self.c_idx_prayer], anchor="w")
        self.prayer_objs = {}
        spacing = self.screen_w // 8
        for i, prayer in enumerate(PRAYER_ORDER):
            p_obj = self.create_shadow_text(spacing * (i + 2), Y_PRAYER, "", ("Arial", 42, "bold"),
                                            COLORS[self.c_idx_prayer], justify="center")
            self.prayer_objs[prayer] = p_obj

        self.iqamath_bg_rect = self.canvas.create_rectangle(0, 0, self.screen_w, self.screen_h, fill="black",
                                                            state='hidden')
        self.iqamath_t = self.canvas.create_text(self.screen_w // 2, self.screen_h // 2, text="",
                                                 font=("Arial", 160, "bold"), fill="white", state='hidden',
                                                 justify="center")

    def toggle_main_ui(self, state):
        items = [self.title_obj["main"], self.clock_obj["main"], self.date_obj["main"], self.hijri_obj["main"],
                 self.bg_img_id, self.ticker_bg, self.full_screen_overlay, self.mode_header["main"]]
        items += self.title_obj["shadows"] + self.clock_obj["shadows"] + self.date_obj["shadows"] + self.hijri_obj[
            "shadows"] + self.mode_header["shadows"]
        for p in self.prayer_objs.values(): items += [p["main"]] + p["shadows"]
        for t in self.ticker_items: items.append(t)
        for i in items: self.canvas.itemconfig(i, state=state)

    def trigger_prayer_alert(self, prayer_name, data):
        self.alert_active = True
        self.canvas.itemconfig(self.iqamath_bg_rect, fill=BG_COLORS[self.c_idx_iqamath_bg], state='normal')
        display_name = "JUMU'AH" if (datetime.now().weekday() == 4 and prayer_name == "Dhuhr") else prayer_name.upper()
        self.canvas.itemconfig(self.iqamath_t, text=f"TIME FOR\n{display_name}", fill=COLORS[self.c_idx_iqamath_text],
                               state='normal', font=("Arial", 140, "bold"))
        self.toggle_main_ui('hidden')
        is_fri = datetime.now().weekday() == 4
        wait_time = data.get("jumuah_iqamath", data["iqamath"]) if (is_fri and prayer_name == "Dhuhr") else data[
            "iqamath"]
        self.root.after(10000, lambda: self.start_iqamath(wait_time))

    def start_iqamath(self, delay):
        self.alert_active = False
        self.iqamath_active = True
        self.iqamath_end_time = datetime.now() + timedelta(minutes=delay)

    def handle_iqamath_display(self, now):
        rem = (self.iqamath_end_time - now).total_seconds()
        theme_color = COLORS[self.c_idx_iqamath_text]
        if rem > 0:
            m, s = divmod(int(rem), 60)
            self.canvas.itemconfig(self.iqamath_t, text=f"IQAMATH IN\n{m:02d}:{s:02d}", fill=theme_color)
        elif rem > -30:
            self.flash_state = not self.flash_state
            self.canvas.itemconfig(self.iqamath_t, text="PRAYER\nSTARTING",
                                   fill=(theme_color if self.flash_state else BG_COLORS[self.c_idx_iqamath_bg]),
                                   font=("Arial", 180, "bold"))
        else:
            self.iqamath_active = False
            self.canvas.itemconfig(self.iqamath_t, state='hidden')
            self.canvas.itemconfig(self.iqamath_bg_rect, state='hidden')
            self.toggle_main_ui('normal')

    def update_clock(self):
        now = datetime.now()

        # Check if the day has changed (Midnight trigger)
        if now.day != self.current_day:
            self.current_day = now.day
            self.fetch_prayer_times()  # Auto-refresh times for the new day

        if self.selected_prayer and (now - self.last_interaction_time).total_seconds() > 10:
            self.selected_prayer = None
            self.apply_colors()

        self.update_shadow_text(self.clock_obj, new_text=now.strftime("%I:%M:%S %p"))
        self.update_shadow_text(self.date_obj, new_text=now.strftime("%A, %B %d, %Y"))
        try:
            h = Gregorian(now.year, now.month, now.day).to_hijri()
            self.update_shadow_text(self.hijri_obj, new_text=f"{h.day} {h.month_name()} {h.year} AH")
        except:
            pass

        if self.iqamath_active:
            self.handle_iqamath_display(now)
        elif not self.preview_mode and not self.alert_active:
            curr_time_str = now.strftime("%H:%M")
            for p, d in self.prayer_data.items():
                if p != "Sunrise" and curr_time_str == f"{d['time'][0]:02d}:{d['time'][1]:02d}":
                    if self.triggering_azan != curr_time_str:
                        self.triggering_azan = curr_time_str
                        self.trigger_prayer_alert(p, d)
            self.update_prayer_list(now)
        self.root.after(1000, self.update_clock)

    def update_prayer_list(self, now):
        is_friday = (now.weekday() == 4)
        show_azan = (now.second % 20) < 10
        self.update_shadow_text(self.mode_header, new_text="Azan" if show_azan else "Iqamath",
                                new_color=COLORS[self.c_idx_prayer])
        for prayer in PRAYER_ORDER:
            h, m = self.prayer_data[prayer]["time"]
            ps = now.replace(hour=h, minute=m, second=0, microsecond=0)
            iq_delay = self.prayer_data[prayer].get(
                "jumuah_iqamath" if (is_friday and prayer == "Dhuhr") else "iqamath", 15)
            iq_time = ps + timedelta(minutes=iq_delay)
            is_high = (ps <= now <= ps + timedelta(minutes=60))
            display_name = "JUMMA" if (is_friday and prayer == "Dhuhr") else prayer
            target_color = "red" if prayer == self.selected_prayer else (
                COLORS[self.c_idx_prayer_high] if is_high else COLORS[self.c_idx_prayer])
            time_val = f"{h:02d}:{m:02d}" if (show_azan or prayer == "Sunrise") else iq_time.strftime('%H:%M')
            self.update_shadow_text(self.prayer_objs[prayer], new_text=f"{display_name}\n{time_val}")
            curr_color = self.canvas.itemcget(self.prayer_objs[prayer]["main"], "fill")
            if curr_color.lower() != target_color.lower(): self.fade_prayer_text(prayer, target_color)

    def show_admin_preview(self, title, detail, is_highlight=False):
        if self.iqamath_active or self.alert_active: return
        self.preview_mode = True
        self.canvas.coords(self.iqamath_bg_rect, 0, 0, self.screen_w, self.screen_h // 3)
        self.canvas.coords(self.iqamath_t, self.screen_w // 2, self.screen_h // 6)
        bg = COLORS[self.c_idx_prayer_high] if is_highlight else BG_COLORS[self.c_idx_iqamath_bg]
        txt = "black" if (is_highlight and COLORS[self.c_idx_prayer_high] in ["white", "gold", "cyan", "#00FF00"]) else \
        COLORS[self.c_idx_iqamath_text]
        self.canvas.itemconfig(self.iqamath_bg_rect, fill=bg, state='normal')
        self.canvas.itemconfig(self.iqamath_t, text=f"{title.upper()}\n{detail}", fill=txt, font=("Arial", 45, "bold"),
                               state='normal')
        if hasattr(self, '_prev_timer'): self.root.after_cancel(self._prev_timer)
        self._prev_timer = self.root.after(2000, self.end_preview)

    def end_preview(self):
        self.preview_mode = False
        self.canvas.itemconfig(self.iqamath_bg_rect, state='hidden')
        self.canvas.itemconfig(self.iqamath_t, state='hidden')

    def create_rich_ticker(self):
        for item in self.ticker_items: self.canvas.delete(item)
        self.ticker_items = []
        segments = re.split(r'(;;|,,)', self.raw_announcements)
        for seg in segments:
            if not seg.strip(): continue
            txt, clr = ((" ★ ", COLORS[self.c_idx_masjid]) if seg == ";;" else (
            " • ", COLORS[self.c_idx_masjid]) if seg == ",," else (seg, "white"))
            t_obj = self.canvas.create_text(self.screen_w, self.ticker_y, text=txt, font=("Arial", 32, "bold"),
                                            fill=clr, anchor="w")
            self.ticker_items.append(t_obj)

    def scroll_ticker(self):
        if self.ticker_items:
            self.ticker_pos -= 2
            curr_x = self.ticker_pos
            for item in self.ticker_items:
                self.canvas.coords(item, curr_x, self.ticker_y)
                bbox = self.canvas.bbox(item)
                if bbox: curr_x += (bbox[2] - bbox[0])
            if self.ticker_pos < -3000: self.ticker_pos = self.screen_w
        self.root.after(30, self.scroll_ticker)

    def apply_colors(self):
        for obj, idx in [(self.title_obj, self.c_idx_masjid), (self.clock_obj, self.c_idx_clock),
                         (self.date_obj, self.c_idx_greg_cal), (self.hijri_obj, self.c_idx_hijri_cal)]:
            self.update_shadow_text(obj, new_color=COLORS[idx])
        self.update_shadow_text(self.mode_header, new_color=COLORS[self.c_idx_prayer])
        self.update_prayer_list(datetime.now())

    def save_settings_to_file(self):
        data = {k: getattr(self, k) for k in
                ["prayer_data", "raw_announcements", "c_idx_masjid", "c_idx_clock", "c_idx_prayer", "c_idx_prayer_high",
                 "c_idx_greg_cal", "c_idx_hijri_cal", "c_idx_iqamath_text", "c_idx_iqamath_bg"]}
        with open(SETTINGS_FILE, "w") as f: json.dump(data, f)

    def load_settings_from_file(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        if hasattr(self, k): setattr(self, k, v)
            except:
                pass

    def cycle_element(self, element):
        if element == "masjid":
            self.c_idx_masjid = (self.c_idx_masjid + 1) % len(COLORS)
        elif element == "clock":
            self.c_idx_clock = (self.c_idx_clock + 1) % len(COLORS)
        elif element == "prayer":
            self.c_idx_prayer = (self.c_idx_prayer + 1) % len(COLORS)
        elif element == "prayer_high":
            self.c_idx_prayer_high = (self.c_idx_prayer_high + 1) % len(COLORS)
            self.show_admin_preview("HIGHLIGHT PREVIEW", "ACTIVE PRAYER COLOR", True)
        elif element == "greg_cal":
            self.c_idx_greg_cal = (self.c_idx_greg_cal + 1) % len(COLORS)
        elif element == "hijri_cal":
            self.c_idx_hijri_cal = (self.c_idx_hijri_cal + 1) % len(COLORS)
        elif element == "count_txt":
            self.c_idx_iqamath_text = (self.c_idx_iqamath_text + 1) % len(COLORS)
            self.show_admin_preview("COUNTDOWN TEXT", f"COLOR: {COLORS[self.c_idx_iqamath_text]}")
        elif element == "count_bg":
            self.c_idx_iqamath_bg = (self.c_idx_iqamath_bg + 1) % len(BG_COLORS)
            self.show_admin_preview("COUNTDOWN BG", "BG COLOR CHANGED")
        self.apply_colors();
        self.save_settings_to_file()

    def handle_keys(self, event):
        if hasattr(self, 'ed') and self.ed.winfo_exists(): return
        self.last_interaction_time = datetime.now()
        char = event.char.lower()
        is_fri = (datetime.now().weekday() == 4)
        if char in "123456": self.selected_prayer = PRAYER_ORDER[int(char) - 1]; self.apply_colors(); return
        if self.selected_prayer:
            p = self.prayer_data[self.selected_prayer]
            f = "jumuah_iqamath" if (is_fri and self.selected_prayer == "Dhuhr") else "iqamath"
            ch = False
            if char == "+":
                p[f] += 1; ch = True
            elif char == "-" and p[f] > 1:
                p[f] -= 1; ch = True
            elif char == "h":
                p["time"][0] = (p["time"][0] + 1) % 24; ch = True
            elif char == "m":
                p["time"][1] = (p["time"][1] + 1) % 60; ch = True
            if ch:
                lbl = "JUMMA IQ" if (is_fri and self.selected_prayer == "Dhuhr") else "IQ"
                self.show_admin_preview(f"EDITING: {self.selected_prayer}",
                                        f"TIME {p['time'][0]:02d}:{p['time'][1]:02d} | {lbl} {p[f]}m")
                self.save_settings_to_file();
                self.apply_colors()
        if char == "t": self.open_announcement_editor()

    def open_announcement_editor(self):
        self.ed = tk.Frame(self.root, bg="#222222", bd=5, relief="ridge")
        self.ed.place(relx=0.5, rely=0.85, anchor="center", width=self.screen_w * 0.95, height=150)
        self.en = tk.Entry(self.ed, font=("Arial", 30), bg="black", fg="white", insertbackground="white")
        self.en.pack(fill="x", padx=20, pady=5);
        self.en.insert(0, self.raw_announcements)
        self.en.focus_set();
        self.en.bind("<Return>", self.save_ann)
        self.en.bind("<Escape>", lambda e: self.ed.destroy())

    def save_ann(self, e):
        self.raw_announcements = self.en.get();
        self.create_rich_ticker();
        self.save_settings_to_file();
        self.ed.destroy()

    def on_escape(self, event):
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MosqueDisplay(root)
    root.mainloop()