# -*- coding: utf-8 -*-
"""جسر — اربط هاتف أندرويد بالحاسوب واعرض شاشته. واجهة فوق scrcpy و ADB."""
import os, re, sys, shutil, subprocess, threading, time
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path

BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
MEI = Path(getattr(sys, "_MEIPASS", BASE))  # الملفات المدمجة داخل exe
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BG, CARD, FG, MUTED, ACC = "#0b0d22", "#151833", "#f2f3ff", "#a2a7c9", "#6d4aff"
FONT = ("Tahoma", 10)


def tool(name):
    exe = name + (".exe" if os.name == "nt" else "")
    for d in (MEI / "tools", BASE / "tools", BASE):
        if (d / exe).exists():
            return str(d / exe)
    return shutil.which(name)


def run(cmd, timeout=30, binary=False):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NOWIN)
        out = r.stdout if binary else (r.stdout + r.stderr).decode("utf-8", "replace")
        return r.returncode, out
    except Exception as e:
        return 1, str(e)


def out_dir(sub):
    base = Path.home() / sub / "Jisr"
    base.mkdir(parents=True, exist_ok=True)
    return base


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("جسر — هاتفك على حاسوبك")
        self.configure(bg=BG)
        self.geometry("520x720")
        self.minsize(480, 640)
        self.adb, self.scrcpy = tool("adb"), tool("scrcpy")
        if self.adb:
            os.environ["ADB"] = self.adb
        self.proc = None
        self.devices = {}
        self._style()
        self._build()
        if not (self.adb and self.scrcpy):
            self.log("⚠ لم أجد adb أو scrcpy داخل البرنامج. أعد تحميل Jisr.exe من الموقع.")
        else:
            self.refresh()
        self.after(1000, self._poll)

    # ---------- الواجهة ----------
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("TLabel", background=CARD, foreground=FG, font=FONT)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=FONT)
        s.configure("Title.TLabel", background=BG, foreground=FG, font=("Tahoma", 20, "bold"))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=FONT)
        s.configure("TCheckbutton", background=CARD, foreground=FG, font=FONT)
        s.map("TCheckbutton", background=[("active", CARD)])
        s.configure("TButton", font=FONT, padding=8, background="#23274a", foreground=FG, borderwidth=0)
        s.map("TButton", background=[("active", "#2f3466")])
        s.configure("Go.TButton", background=ACC, foreground="#fff", font=("Tahoma", 11, "bold"), padding=10)
        s.map("Go.TButton", background=[("active", "#7d5dff")])
        s.configure("TCombobox", padding=4)

    def card(self, title):
        f = ttk.Frame(self, style="Card.TFrame", padding=12)
        f.pack(fill="x", padx=16, pady=6)
        ttk.Label(f, text=title, font=("Tahoma", 11, "bold")).pack(anchor="e", pady=(0, 8))
        return f

    def _build(self):
        ttk.Label(self, text="✦ جسر", style="Title.TLabel").pack(anchor="e", padx=16, pady=(16, 0))
        ttk.Label(self, text="اعرض شاشة هاتفك على الحاسوب وتحكم بها", style="Sub.TLabel").pack(anchor="e", padx=16)

        c = self.card("١. الجهاز")
        row = ttk.Frame(c, style="Card.TFrame"); row.pack(fill="x")
        ttk.Button(row, text="تحديث", command=self.refresh).pack(side="left")
        self.dev = ttk.Combobox(row, state="readonly", justify="right")
        self.dev.pack(side="right", fill="x", expand=True, padx=(0, 8))
        ttk.Label(c, text="وصّل الهاتف بكابل USB وفعّل «تصحيح USB» من خيارات المطور.", style="Muted.TLabel").pack(anchor="e", pady=(6, 0))

        c = self.card("٢. الاتصال اللاسلكي (اختياري)")
        row = ttk.Frame(c, style="Card.TFrame"); row.pack(fill="x")
        ttk.Button(row, text="اتصال", command=self.wifi_connect).pack(side="left")
        self.ip = ttk.Entry(row, justify="left"); self.ip.pack(side="right", fill="x", expand=True, padx=(0, 8))
        ttk.Label(c, text="عنوان الهاتف مثل 192.168.1.5:5555", style="Muted.TLabel").pack(anchor="e", pady=(6, 4))
        ttk.Button(c, text="تحويل الكابل إلى لاسلكي تلقائياً", command=self.to_wifi).pack(fill="x")

        c = self.card("٣. الخيارات")
        g = ttk.Frame(c, style="Card.TFrame"); g.pack(fill="x")
        self.size = self._opt(g, 0, "دقة العرض", ["الأصلية", "1920", "1280", "1024"], "1280")
        self.rate = self._opt(g, 1, "جودة الفيديو (Mbps)", ["4", "8", "16", "24"], "8")
        self.fps = self._opt(g, 2, "عدد الإطارات", ["30", "60"], "60")
        self.v_off = tk.BooleanVar(); self.v_awake = tk.BooleanVar(value=True)
        self.v_top = tk.BooleanVar(); self.v_rec = tk.BooleanVar()
        for t, v in (("إطفاء شاشة الهاتف أثناء العرض", self.v_off), ("إبقاء الهاتف مستيقظاً", self.v_awake),
                     ("إبقاء النافذة فوق كل شيء", self.v_top), ("تسجيل الشاشة إلى ملف فيديو", self.v_rec)):
            ttk.Checkbutton(c, text=t, variable=v).pack(anchor="e", pady=1)

        row = ttk.Frame(self); row.pack(fill="x", padx=16, pady=8)
        self.btn = ttk.Button(row, text="▶  ابدأ عرض الشاشة", style="Go.TButton", command=self.toggle)
        self.btn.pack(fill="x")
        row = ttk.Frame(self); row.pack(fill="x", padx=16)
        ttk.Button(row, text="📷 لقطة شاشة", command=self.shot).pack(side="right", expand=True, fill="x", padx=(4, 0))
        ttk.Button(row, text="📁 إرسال ملفات للهاتف", command=self.push).pack(side="left", expand=True, fill="x", padx=(0, 4))

        self.status = ttk.Label(self, text="جاهز", style="Sub.TLabel"); self.status.pack(anchor="e", padx=16, pady=(8, 0))
        self.logbox = tk.Text(self, height=7, bg=CARD, fg=MUTED, bd=0, font=("Consolas", 9), wrap="word")
        self.logbox.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        self.logbox.configure(state="disabled")

    def _opt(self, parent, r, label, vals, default):
        cb = ttk.Combobox(parent, values=vals, state="readonly", width=10, justify="center")
        cb.set(default); cb.grid(row=r, column=0, sticky="w", pady=3)
        ttk.Label(parent, text=label).grid(row=r, column=1, sticky="e", padx=(12, 0))
        parent.columnconfigure(1, weight=1)
        return cb

    # ---------- مساعدات ----------
    def log(self, msg):
        def w():
            self.logbox.configure(state="normal")
            self.logbox.insert("end", msg + "\n"); self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.after(0, w)

    def serial(self):
        return self.devices.get(self.dev.get())

    def need(self):
        if not (self.adb and self.scrcpy):
            self.log("⚠ الأدوات غير موجودة."); return None
        s = self.serial()
        if not s:
            self.log("⚠ اختر جهازاً أولاً (اضغط تحديث)."); return None
        return s

    def bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ---------- الأوامر ----------
    def refresh(self):
        def job():
            run([self.adb, "start-server"])
            code, out = run([self.adb, "devices", "-l"])
            self.devices = {}
            for line in out.splitlines()[1:]:
                p = line.split()
                if len(p) < 2: continue
                m = re.search(r"model:(\S+)", line)
                name = f"{(m.group(1) if m else 'Android').replace('_', ' ')} — {p[0]}"
                if p[1] == "device": self.devices[name] = p[0]
                elif p[1] == "unauthorized": self.log("⚠ وافق على نافذة «السماح بتصحيح USB» في هاتفك.")
            names = list(self.devices)
            def ui():
                self.dev["values"] = names
                self.dev.set(names[0] if names else "")
            self.after(0, ui)
            self.log(f"تم العثور على {len(names)} جهاز." if names else "لا يوجد جهاز متصل.")
        if self.adb: self.bg(job)

    def wifi_connect(self):
        addr = self.ip.get().strip()
        if not addr: return self.log("اكتب عنوان الهاتف أولاً.")
        def job():
            _, out = run([self.adb, "connect", addr]); self.log(out.strip()); self.refresh()
        self.bg(job)

    def to_wifi(self):
        s = self.need()
        if not s: return
        def job():
            _, out = run([self.adb, "-s", s, "shell", "ip", "route"])
            m = re.search(r"src (\d+\.\d+\.\d+\.\d+)", out)
            if not m: return self.log("تعذر معرفة عنوان الهاتف. تأكد من اتصاله بنفس شبكة الواي فاي.")
            addr = f"{m.group(1)}:5555"
            run([self.adb, "-s", s, "tcpip", "5555"]); time.sleep(2)
            _, o = run([self.adb, "connect", addr]); self.log(o.strip())
            self.after(0, lambda: (self.ip.delete(0, "end"), self.ip.insert(0, addr)))
            self.log("يمكنك الآن فصل الكابل."); self.refresh()
        self.bg(job)

    def toggle(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate(); return
        s = self.need()
        if not s: return
        a = [self.scrcpy, "-s", s, "--window-title", "جسر"]
        if self.size.get() != "الأصلية": a += ["--max-size", self.size.get()]
        a += ["--video-bit-rate", self.rate.get() + "M", "--max-fps", self.fps.get()]
        if self.v_off.get(): a.append("--turn-screen-off")
        if self.v_awake.get(): a.append("--stay-awake")
        if self.v_top.get(): a.append("--always-on-top")
        if self.v_rec.get():
            f = out_dir("Videos") / time.strftime("jisr_%Y%m%d_%H%M%S.mp4")
            a.append(f"--record={f}"); self.log(f"التسجيل إلى: {f}")
        try:
            self.proc = subprocess.Popen(a, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NOWIN)
        except Exception as e:
            return self.log(f"فشل التشغيل: {e}")
        self.btn.configure(text="■  أوقف العرض"); self.status.configure(text="● جارٍ العرض")
        def reader():
            for line in self.proc.stdout:
                self.log(line.decode("utf-8", "replace").rstrip())
        self.bg(reader)

    def _poll(self):
        if self.proc and self.proc.poll() is not None:
            self.proc = None
            self.btn.configure(text="▶  ابدأ عرض الشاشة"); self.status.configure(text="جاهز")
        self.after(1000, self._poll)

    def shot(self):
        s = self.need()
        if not s: return
        def job():
            code, data = run([self.adb, "-s", s, "exec-out", "screencap", "-p"], binary=True)
            if code or not data: return self.log("فشل أخذ اللقطة.")
            f = out_dir("Pictures") / time.strftime("jisr_%Y%m%d_%H%M%S.png")
            f.write_bytes(data); self.log(f"حُفظت اللقطة: {f}")
        self.bg(job)

    def push(self):
        s = self.need()
        if not s: return
        files = filedialog.askopenfilenames(title="اختر ملفات لإرسالها إلى الهاتف")
        def job():
            for f in files:
                _, o = run([self.adb, "-s", s, "push", f, "/sdcard/Download/"], timeout=600)
                self.log(o.strip().splitlines()[-1] if o.strip() else "تم")
            if files: self.log("الملفات في مجلد Download على الهاتف.")
        if files: self.bg(job)


if __name__ == "__main__":
    App().mainloop()
