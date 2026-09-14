# -*- coding: utf-8 -*-
"""Desktop app: PC audio -> Phone -> Bluetooth earphones."""
import json
import os
import threading
import tkinter as tk
from tkinter import messagebox

import server

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PCPhoneAudio")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")


def load_settings():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

S = {
"ar": {"title": "صوت الحاسوب إلى الهاتف", "sub": "استمع لصوت حاسوبك من سماعات البلوتوث المربوطة بهاتفك.",
"step1t": "نفس الواي فاي", "step1d": "الهاتف والحاسوب على نفس الشبكة",
"step2t": "اربط السماعات", "step2d": "سماعات البلوتوث مربوطة بالهاتف",
"step3t": "أدخل الرمز وشغّل", "step3d": "امسح QR من الهاتف ثم اضغط تشغيل",
"pin": "الرمز", "url": "رابط الهاتف", "copy": "نسخ الرابط", "copied": "تم نسخ الرابط — أرسله إلى هاتفك.",
"start": "تشغيل", "stop": "إيقاف", "running": "● يعمل", "stopped": "○ متوقف",
"clients": "هواتف متصلة", "audio": "الصوت", "audio_wait": "بانتظار الالتقاط…",
"theme": "داكن", "theme_l": "فاتح", "footer": "إغلاق النافذة يوقف التطبيق",
"mode_note": "من الهاتف: مباشر للشاشة المضيئة، خلفية مع قفل الشاشة"},
"en": {"title": "PC Audio to Phone", "sub": "Hear your PC on the Bluetooth earphones paired with your phone.",
"step1t": "Same Wi-Fi", "step1d": "Phone and PC on the same network",
"step2t": "Pair the buds", "step2d": "Bluetooth earphones paired with the phone",
"step3t": "Enter code & play", "step3d": "Scan the QR from your phone, then press play",
"pin": "Code", "url": "Phone link", "copy": "Copy link", "copied": "Link copied — send it to your phone.",
"start": "Start", "stop": "Stop", "running": "● Running", "stopped": "○ Stopped",
"clients": "Connected phones", "audio": "Audio", "audio_wait": "Waiting for capture…",
"theme": "Dark", "theme_l": "Light", "footer": "Closing the window stops the app",
"mode_note": "On the phone: Instant for screen-on, Background with locked screen"},
"fr": {"title": "Audio du PC vers le téléphone", "sub": "Écoutez votre PC sur les écouteurs Bluetooth associés à votre téléphone.",
"step1t": "Même Wi-Fi", "step1d": "Téléphone et PC sur le même réseau",
"step2t": "Associez les écouteurs", "step2d": "Écouteurs Bluetooth associés au téléphone",
"step3t": "Code et lecture", "step3d": "Scannez le QR depuis le téléphone, puis lancez la lecture",
"pin": "Code", "url": "Lien du téléphone", "copy": "Copier le lien", "copied": "Lien copié — envoyez-le à votre téléphone.",
"start": "Démarrer", "stop": "Arrêter", "running": "● En cours", "stopped": "○ Arrêté",
"clients": "Téléphones connectés", "audio": "Audio", "audio_wait": "En attente de capture…",
"theme": "Sombre", "theme_l": "Clair", "footer": "Fermer la fenêtre arrête l'application",
"mode_note": "Sur le téléphone : Direct écran allumé, Arrière-plan écran verrouillé"},
"es": {"title": "Audio del PC al teléfono", "sub": "Escucha tu PC en los auriculares Bluetooth vinculados a tu teléfono.",
"step1t": "Mismo Wi-Fi", "step1d": "Teléfono y PC en la misma red",
"step2t": "Vincula los auriculares", "step2d": "Auriculares Bluetooth vinculados al teléfono",
"step3t": "Código y reproducir", "step3d": "Escanea el QR desde el teléfono y pulsa reproducir",
"pin": "Código", "url": "Enlace del teléfono", "copy": "Copiar enlace", "copied": "Enlace copiado — envíalo a tu teléfono.",
"start": "Iniciar", "stop": "Detener", "running": "● En curso", "stopped": "○ Detenido",
"clients": "Teléfonos conectados", "audio": "Audio", "audio_wait": "Esperando captura…",
"theme": "Oscuro", "theme_l": "Claro", "footer": "Cerrar la ventana detiene la aplicación",
"mode_note": "En el teléfono: Directo con pantalla encendida, Fondo con pantalla bloqueada"},
}

THEMES = {
"dark": {"bg": "#0a0a0a", "surface": "#141414", "raised": "#1c1c1c",
         "border": "#262626", "fg": "#e5e5e5", "muted": "#a1a1a1"},
"light": {"bg": "#ffffff", "surface": "#f5f5f5", "raised": "#ececec",
          "border": "#e2e2e2", "fg": "#0a0a0a", "muted": "#525252"},
}
LANGS = [("العربية", "ar"), ("English", "en"), ("Français", "fr"), ("Español", "es")]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        settings = load_settings()
        self.lang = settings.get("lang") if settings.get("lang") in S else None
        self.theme = settings.get("theme", "dark")
        if self.theme not in THEMES:
            self.theme = "dark"
        self.running = False
        self._closed = False
        self.geometry("400x735")
        self.resizable(False, False)
        self._build()
        if not self.lang:
            self._first_run_language()
        if not self.lang:
            self.lang = "en"
        self._sync_lang_menu()
        self.apply_all()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(500, self.start_server)

    def t(self, k):
        return S[self.lang].get(k, S["en"].get(k, k))

    def pal(self):
        return THEMES[self.theme]

    def _first_run_language(self):
        """Modal language picker shown once when no saved preference exists."""
        self.withdraw()
        d = tk.Toplevel(self)
        d.title("Language")
        d.geometry("320x320")
        d.resizable(False, False)
        # NOTE: no transient() here — a transient of a withdrawn master
        # stays invisible on Windows and would block the app forever.
        d.attributes("-topmost", True)
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            d.geometry(f"320x320+{(sw - 320) // 2}+{(sh - 320) // 2}")
        except Exception:
            pass
        p = self.pal()
        d.configure(bg=p["bg"])
        tk.Label(d, text="Choose language", font=("Segoe UI", 13, "bold"),
                 bg=p["bg"], fg=p["fg"]).pack(pady=(16, 4))
        tk.Label(d, text="اختر اللغة", font=("Segoe UI", 11),
                 bg=p["bg"], fg=p["muted"]).pack(pady=(0, 10))
        for name, code in LANGS:
            b = tk.Button(d, text=name, font=("Segoe UI", 12), pady=7,
                          bg=p["raised"], fg=p["fg"], activebackground=p["border"],
                          activeforeground=p["fg"], relief="flat", bd=0,
                          highlightthickness=1, highlightbackground=p["border"],
                          command=lambda c=code: self._choose_first_lang(d, c))
            b.pack(fill="x", padx=24, pady=4)
        d.grab_set()
        self.wait_window(d)
        self.deiconify()
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(1500, lambda: self.attributes("-topmost", False) if not self._closed else None)
        except Exception:
            pass

    def _choose_first_lang(self, dialog, code):
        self.lang = code
        save_settings({"lang": code, "theme": self.theme})
        try:
            dialog.destroy()
        except Exception:
            pass

    def _sync_lang_menu(self):
        for name, code in LANGS:
            if code == self.lang:
                self.lang_v.set(name)
                break

    def _card(self):
        f = tk.Frame(self, highlightthickness=1, bd=0, padx=12, pady=8)
        f.pack(fill="x", padx=12, pady=6)
        return f

    def _hover(self, b):
        b.bind("<Enter>", lambda e, bb=b: bb.configure(highlightbackground=self.pal()["fg"]))
        b.bind("<Leave>", lambda e, bb=b: bb.configure(highlightbackground=self.pal()["border"]))

    def _build(self):
        self.top = tk.Frame(self)
        self.top.pack(fill="x", padx=12, pady=(12, 2))
        self.title_l = tk.Label(self.top, font=("Segoe UI", 15, "bold"))
        self.title_l.pack(side="left")
        self.ctrls = tk.Frame(self.top)
        self.ctrls.pack(side="right")
        self.theme_b = tk.Button(self.ctrls, text="☾", width=3, command=self.toggle_theme)
        self.theme_b.pack(side="left", padx=2)
        self.lang_v = tk.StringVar(value="العربية")
        self.lang_m = tk.OptionMenu(self.ctrls, self.lang_v,
                                    *[n for n, _ in LANGS], command=self.set_lang)
        self.lang_m.configure(relief="flat", bd=0, highlightthickness=1)
        self.lang_m.pack(side="left", padx=2)

        self.sub_l = tk.Label(self, font=("Segoe UI", 10), wraplength=360, justify="center")
        self.sub_l.pack(pady=(2, 8))

        self.status = tk.Label(self, font=("Segoe UI", 11, "bold"), pady=7)
        self.status.pack(fill="x", padx=12, pady=2)

        self.steps_card = self._card()
        self.steps_f = tk.Frame(self.steps_card)
        self.steps_f.pack(fill="x")
        self.step_rows = []
        for i in range(3):
            r = tk.Frame(self.steps_f)
            r.pack(fill="x", pady=3)
            num = tk.Label(r, text=str(i + 1), font=("Consolas", 11, "bold"), width=3)
            num.pack(side="left")
            box = tk.Frame(r)
            box.pack(side="left", fill="x", expand=True, padx=(8, 0))
            tt = tk.Label(box, font=("Segoe UI", 10, "bold"), anchor="w")
            tt.pack(fill="x")
            dd = tk.Label(box, font=("Segoe UI", 9), anchor="w")
            dd.pack(fill="x")
            self.step_rows.append((num, tt, dd))

        self.pin_card = self._card()
        self.pin_l = tk.Label(self.pin_card, font=("Segoe UI", 10))
        self.pin_l.pack()
        self.pin_v = tk.Label(self.pin_card, text="••••••", font=("Consolas", 30, "bold"))
        self.pin_v.pack(pady=(0, 4))
        self.url_l = tk.Label(self.pin_card, font=("Segoe UI", 10))
        self.url_l.pack()
        self.url_v = tk.Label(self.pin_card, text="—", font=("Consolas", 9))
        self.url_v.pack()
        self.copy_b = tk.Button(self.pin_card, command=self.copy_url, font=("Segoe UI", 10), pady=5)
        self.copy_b.pack(pady=(6, 2))
        qrbox = tk.Frame(self.pin_card, bg="white", padx=6, pady=6)
        qrbox.pack(pady=(6, 0))
        self.qr_l = tk.Label(qrbox, bg="white")
        self.qr_l.pack()

        self.metarow = tk.Frame(self)
        self.metarow.pack(pady=8)
        self.cli_l = tk.Label(self.metarow, font=("Segoe UI", 10))
        self.cli_l.pack(pady=1)
        self.aud_l = tk.Label(self.metarow, font=("Segoe UI", 10))
        self.aud_l.pack(pady=1)

        self.toggle = tk.Button(self, command=self.on_toggle,
                                font=("Segoe UI", 12, "bold"), pady=8)
        self.toggle.pack(fill="x", padx=12, pady=2)

        self.note_l = tk.Label(self, font=("Segoe UI", 9), wraplength=360, justify="center")
        self.note_l.pack(pady=4)
        self.foot_l = tk.Label(self, font=("Segoe UI", 9))
        self.foot_l.pack(side="bottom", pady=8)
        for b in (self.theme_b, self.copy_b, self.toggle):
            self._hover(b)

    def apply_all(self):
        p = self.pal()
        self.configure(bg=p["bg"])
        for w in (self.top, self.ctrls, self.metarow):
            w.configure(bg=p["bg"])
        for w in (self.sub_l, self.title_l,
                  self.cli_l, self.aud_l, self.note_l, self.foot_l):
            w.configure(bg=p["bg"], fg=p["fg"])
        for c in (self.steps_card, self.pin_card):
            c.configure(bg=p["surface"], highlightbackground=p["border"])
        self.steps_f.configure(bg=p["surface"])
        for r in self.steps_f.winfo_children():
            r.configure(bg=p["surface"])
            for c in r.winfo_children():
                if isinstance(c, tk.Frame):
                    c.configure(bg=p["surface"])
                else:
                    c.configure(bg=p["raised"], fg=p["fg"])
        for _, tt, dd in self.step_rows:
            tt.configure(bg=p["surface"], fg=p["fg"])
            dd.configure(bg=p["surface"], fg=p["muted"])
        for w in (self.pin_l, self.pin_v, self.url_l, self.url_v):
            w.configure(bg=p["surface"], fg=p["fg"])
        for w in (self.sub_l, self.note_l, self.foot_l, self.pin_l, self.url_l):
            w.configure(fg=p["muted"])
        for b in (self.theme_b, self.copy_b, self.toggle):
            b.configure(bg=p["raised"], fg=p["fg"], activebackground=p["border"],
                        activeforeground=p["fg"], relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=p["border"])
        self.lang_m.configure(bg=p["raised"], fg=p["fg"], activebackground=p["border"],
                              activeforeground=p["fg"], highlightbackground=p["border"])
        try:
            menu = self.lang_m["menu"]
            menu.configure(bg=p["surface"], fg=p["fg"], activebackground=p["border"],
                           activeforeground=p["fg"], relief="flat", bd=0)
        except Exception:
            pass
        self.title_l.configure(text=self.t("title"))
        side_t = "right" if self.lang == "ar" else "left"
        side_c = "left" if self.lang == "ar" else "right"
        self.title_l.pack_forget()
        self.ctrls.pack_forget()
        self.title_l.pack(side=side_t)
        self.ctrls.pack(side=side_c)
        self.sub_l.configure(text=self.t("sub"))
        for (n, tt, dd), k in zip(self.step_rows,
                                  [("step1t", "step1d"), ("step2t", "step2d"), ("step3t", "step3d")]):
            tt.configure(text=self.t(k[0]))
            dd.configure(text=self.t(k[1]))
        self.pin_l.configure(text=self.t("pin"))
        self.url_l.configure(text=self.t("url"))
        self.copy_b.configure(text=self.t("copy"))
        self.note_l.configure(text=self.t("mode_note"))
        self.foot_l.configure(text=self.t("footer"))
        self.theme_b.configure(text="☀" if self.theme == "dark" else "☾")
        self.refresh_status()
        self.refresh_counts()

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        save_settings({"lang": self.lang, "theme": self.theme})
        self.apply_all()

    def set_lang(self, name):
        for n, c in LANGS:
            if n == name:
                self.lang = c
        save_settings({"lang": self.lang, "theme": self.theme})
        self.apply_all()

    def refresh_status(self):
        p = self.pal()
        if self.running:
            self.status.configure(text=self.t("running"), bg="#0f2a1a", fg="#4ade80")
            self.toggle.configure(text="■ " + self.t("stop"))
        else:
            self.status.configure(text=self.t("stopped"), bg=p["raised"], fg=p["muted"])
            self.toggle.configure(text="▶ " + self.t("start"))

    def refresh_counts(self):
        try:
            with server.connected_lock:
                n = server.connected_count
            ac = server.audio_conf
            au = f"{ac['rate'] // 1000}kHz" if ac.get("ok") else self.t("audio_wait")
            self.cli_l.configure(text=f"{self.t('clients')}: {n}")
            self.aud_l.configure(text=f"{self.t('audio')}: {au}")
        except Exception:
            pass

    def start_server(self):
        if self._closed or self.running:
            return
        pin = server.new_session()
        threading.Thread(target=server.start_background, daemon=True).start()
        self.running = True
        self.pin_v.configure(text=pin)
        url = server.PHONE_URLS[0] if server.PHONE_URLS else "…"
        self.url_v.configure(text=url)
        self._show_qr()
        self.refresh_status()
        self._tick()

    def _show_qr(self):
        try:
            from PIL import Image, ImageTk
            import io
            img = Image.open(io.BytesIO(server.qr_png_bytes)).resize((160, 160))
            self._qr = ImageTk.PhotoImage(img)
            self.qr_l.configure(image=self._qr, text="")
        except Exception:
            self.qr_l.configure(text="QR —")

    def _tick(self):
        if self._closed or not self.running:
            return
        self.refresh_counts()
        self.after(2000, self._tick)

    def on_toggle(self):
        if self.running:
            server.stop_background()
            self.running = False
            self.refresh_status()
        else:
            self.start_server()

    def copy_url(self):
        url = server.PHONE_URLS[0] if server.PHONE_URLS else ""
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)
            messagebox.showinfo(self.t("copy"), self.t("copied"))

    def on_close(self):
        self._closed = True
        try:
            server.stop_background()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
