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
PRESETS = {  # (الدقة، الجودة Mbps، الإطارات، بدون صوت)
    "ألعاب — الأخف على الهاتف": ("720", "4", "30", True),
    "متوازن": ("1024", "6", "45", True),
    "جودة عالية": ("1920", "16", "60", False),
}


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
        self.geometry("500x680")
        self.minsize(460, 560)
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
        # السجل والحالة أولاً في الأسفل حتى يبقيا ظاهرين دائماً
        self.logbox = tk.Text(self, height=7, bg=CARD, fg=MUTED, bd=0, font=("Consolas", 9), wrap="word")
        self.logbox.pack(side="bottom", fill="x", padx=16, pady=(4, 12))
        self.logbox.configure(state="disabled")
        self.status = ttk.Label(self, text="جاهز", style="Sub.TLabel")
        self.status.pack(side="bottom", anchor="e", padx=16)

        ttk.Label(self, text="✦ جسر", style="Title.TLabel").pack(anchor="e", padx=16, pady=(10, 0))
        ttk.Label(self, text="اعرض شاشة هاتفك على الحاسوب وتحكم بها", style="Sub.TLabel").pack(anchor="e", padx=16)

        self.dev_card = self.card("١. الجهاز")
        c = self.dev_card
        row = ttk.Frame(c, style="Card.TFrame"); row.pack(fill="x")
        ttk.Button(row, text="تحديث", command=self.refresh).pack(side="left")
        ttk.Button(row, text="📶 لاسلكي", command=self.wifi_wizard).pack(side="left", padx=(6, 6))
        self.dev = ttk.Combobox(row, state="readonly", justify="right")
        self.dev.pack(side="right", fill="x", expand=True, padx=(0, 8))
        ttk.Label(c, text="وصّل الهاتف بكابل USB وفعّل «تصحيح USB».", style="Muted.TLabel").pack(anchor="e", pady=(6, 0))

        c = self.card("٢. الخيارات")
        pr = ttk.Frame(c, style="Card.TFrame"); pr.pack(fill="x", pady=(0, 8))
        self.preset = ttk.Combobox(pr, values=list(PRESETS), state="readonly", justify="center")
        self.preset.pack(side="left", fill="x", expand=True)
        ttk.Label(pr, text="نمط الأداء").pack(side="right", padx=(8, 0))
        g = ttk.Frame(c, style="Card.TFrame"); g.pack(fill="x")
        self.size = self._opt(g, 0, "دقة العرض", ["الأصلية", "1920", "1280", "1024", "720", "480"], "720")
        self.rate = self._opt(g, 1, "الجودة (Mbps)", ["2", "4", "6", "8", "16", "24"], "4")
        self.fps = self._opt(g, 2, "الإطارات", ["20", "30", "45", "60"], "30")
        self.v_off = tk.BooleanVar(); self.v_awake = tk.BooleanVar(value=True)
        self.v_top = tk.BooleanVar(); self.v_rec = tk.BooleanVar(); self.v_noaudio = tk.BooleanVar(value=True)
        self.v_hw = tk.BooleanVar(value=True); self.v_low = tk.BooleanVar()
        ck = ttk.Frame(c, style="Card.TFrame"); ck.pack(fill="x", pady=(8, 0))
        items = (("إطفاء شاشة الهاتف", self.v_off), ("تسجيل فيديو", self.v_rec),
                 ("بدون صوت (أخف)", self.v_noaudio), ("ترميز بالعتاد (أسرع)", self.v_hw),
                 ("أولوية منخفضة (لألعاب الحاسوب)", self.v_low))
        for i, (t, v) in enumerate(items):
            ttk.Checkbutton(ck, text=t, variable=v).grid(row=i // 2, column=1 - (i % 2), sticky="e", padx=6, pady=1)
        ck.columnconfigure(0, weight=1); ck.columnconfigure(1, weight=1)
        self.preset.bind("<<ComboboxSelected>>", self.apply_preset)
        self.preset.set(list(PRESETS)[0])
        self.apply_preset()

        row = ttk.Frame(self); row.pack(fill="x", padx=16, pady=8)
        self.btn = ttk.Button(row, text="▶  ابدأ عرض الشاشة", style="Go.TButton", command=self.toggle)
        self.btn.pack(fill="x")
        row = ttk.Frame(self); row.pack(fill="x", padx=16)
        ttk.Button(row, text="📷 لقطة", command=self.shot).pack(side="right", expand=True, fill="x", padx=(4, 0))
        ttk.Button(row, text="📁 إرسال ملفات", command=self.push).pack(side="right", expand=True, fill="x", padx=(4, 0))
        ttk.Button(row, text="🩺 تشخيص", command=self.diag).pack(side="right", expand=True, fill="x", padx=(4, 0))


    def apply_preset(self, *_):
        size, rate, fps, noaudio = PRESETS[self.preset.get()]
        self.size.set(size); self.rate.set(rate); self.fps.set(fps); self.v_noaudio.set(noaudio)

    def _opt(self, parent, col, label, vals, default):
        f = ttk.Frame(parent, style="Card.TFrame"); f.grid(row=0, column=2 - col, padx=6, sticky="ew")
        ttk.Label(f, text=label).pack(anchor="e")
        cb = ttk.Combobox(f, values=vals, state="readonly", width=9, justify="center")
        cb.set(default); cb.pack(fill="x")
        parent.columnconfigure(2 - col, weight=1)
        return cb

    # ---------- مساعدات ----------
    def log(self, msg):
        def w():
            self.logbox.configure(state="normal")
            self.logbox.insert("end", msg + "\n"); self.logbox.see("end")
            if int(self.logbox.index("end-1c").split(".")[0]) > 300: self.logbox.delete("1.0", "100.0")
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

    # ---------- الاتصال اللاسلكي (معالج بسيط) ----------
    def say(self, t):
        self.log(t)
        def u():
            if getattr(self, "wz", None) and self.wz.winfo_exists():
                self.wz_msg.configure(text=t)
        self.after(0, u)

    def find(self, kind, timeout):
        """يبحث عن الهاتف في الشبكة تلقائياً (kind: pairing أو connect)."""
        pat = re.compile(r"_adb-tls-%s\._tcp\.?\s+(\d+\.\d+\.\d+\.\d+:\d+)" % kind)
        end = time.time() + timeout
        while time.time() < end:
            _, o = run([self.adb, "mdns", "services"], timeout=10)
            m = pat.search(o)
            if m:
                return m.group(1)
            time.sleep(1.5)
        return None

    def wifi_wizard(self):
        if not self.adb:
            return self.log("⚠ adb غير موجود.")
        if getattr(self, "wz", None) and self.wz.winfo_exists():
            self.wz.lift(); return
        w = self.wz = tk.Toplevel(self)
        w.title("اتصال لاسلكي"); w.configure(bg=BG); w.geometry("470x600"); w.transient(self)
        f = ttk.Frame(w, style="Card.TFrame", padding=14); f.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(f, text="اربط هاتفك بدون كابل", font=("Tahoma", 14, "bold")).pack(anchor="e")
        ttk.Label(f, text="أندرويد 11 أو أحدث، والهاتف والحاسوب على نفس الواي فاي", style="Muted.TLabel").pack(anchor="e", pady=(0, 10))
        for t in ("١) في الهاتف: الإعدادات ← خيارات المطور ← «التصحيح اللاسلكي» وفعّله.",
                  "٢) اضغط «الاقتران برمز الاقتران» وابقَ في تلك الشاشة.",
                  "٣) اكتب الرمز (6 أرقام) هنا ثم اضغط «اربط»:"):
            ttk.Label(f, text=t, wraplength=420, justify="right").pack(anchor="e", pady=2)
        self.wz_code = ttk.Entry(f, justify="center", font=("Consolas", 20), width=8)
        self.wz_code.pack(pady=10); self.wz_code.focus_set()
        ttk.Button(f, text="🔗  اربط الهاتف", style="Go.TButton", command=self.wz_go).pack(fill="x")
        self.wz_msg = ttk.Label(f, text="", style="Muted.TLabel", wraplength=420, justify="right")
        self.wz_msg.pack(anchor="e", pady=8)
        ttk.Button(f, text="🔄 اتصال سريع (هاتف سبق ربطه)", command=self.wz_quick).pack(fill="x", pady=(4, 4))
        ttk.Button(f, text="🔌 لديّ كابل: حوّله إلى لاسلكي", command=self.to_wifi).pack(fill="x")
        ttk.Label(f, text="لم يُكتشف الهاتف؟ اكتب العناوين من شاشة الهاتف (اختياري):", style="Muted.TLabel", wraplength=420, justify="right").pack(anchor="e", pady=(12, 2))
        self.m_pair = ttk.Entry(f, justify="left"); self.m_pair.pack(fill="x")
        ttk.Label(f, text="↑ عنوان الاقتران، مثل 192.168.1.7:38291", style="Muted.TLabel").pack(anchor="e")
        self.m_conn = ttk.Entry(f, justify="left"); self.m_conn.pack(fill="x", pady=(6, 0))
        ttk.Label(f, text="↑ عنوان الاتصال، مثل 192.168.1.7:41999", style="Muted.TLabel").pack(anchor="e")

    def wz_go(self):
        code = self.wz_code.get().strip()
        if not re.fullmatch(r"\d{6}", code):
            return self.say("اكتب الرمز: 6 أرقام بالضبط كما يظهر في الهاتف.")
        pa, ca = self.m_pair.get().strip(), self.m_conn.get().strip()
        def job():
            self.say("🔎 أبحث عن هاتفك…")
            addr = pa or self.find("pairing", 12)
            if not addr:
                return self.say("لم أجد الهاتف. تأكد أنك داخل شاشة «الاقتران برمز الاقتران» وأن الشبكة واحدة، أو اكتب عنوان الاقتران يدوياً بالأسفل.")
            self.say(f"وجدت الهاتف ({addr.split(':')[0]}). جارٍ الاقتران…")
            _, o = run([self.adb, "pair", addr, code], timeout=40)
            if "uccessfully" not in o:
                return self.say("فشل الاقتران. الرمز يتغير كل مرة: أغلق نافذة الاقتران في الهاتف وافتحها من جديد وأعد المحاولة.")
            self.say("تم الاقتران ✔ جارٍ الاتصال…")
            self.wz_connect(ca)
        self.bg(job)

    def wz_quick(self):
        ca = self.m_conn.get().strip()
        self.bg(lambda: (self.say("🔎 أبحث عن هاتفك…"), self.wz_connect(ca)))

    def wz_connect(self, manual=""):
        addr = manual or self.find("connect", 15)
        if not addr:
            return self.say("لم أجد عنوان الاتصال. تأكد أن «التصحيح اللاسلكي» مفعّل، أو اكتب عنوان الاتصال (الذي تحت اسم جهازك) يدوياً.")
        _, o = run([self.adb, "connect", addr], timeout=30)
        if "connected to" in o:
            self.say("✔ تم الاتصال! يمكنك الآن الضغط على «ابدأ عرض الشاشة».")
            self.refresh()
            self.after(1800, lambda: self.wz.destroy() if getattr(self, "wz", None) and self.wz.winfo_exists() else None)
        else:
            self.say("تعذر الاتصال: " + (o.strip().splitlines()[-1] if o.strip() else "بدون رد"))

    def to_wifi(self):
        s = self.need()
        if not s: return
        def job():
            _, out = run([self.adb, "-s", s, "shell", "ip", "route"])
            m = re.search(r"src (\d+\.\d+\.\d+\.\d+)", out)
            if not m: return self.say("تعذر معرفة عنوان الهاتف. تأكد من اتصاله بنفس الواي فاي.")
            addr = f"{m.group(1)}:5555"
            run([self.adb, "-s", s, "tcpip", "5555"]); time.sleep(2)
            _, o = run([self.adb, "connect", addr])
            self.say(o.strip() + " — يمكنك فصل الكابل الآن."); self.refresh()
        self.bg(job)

    def hw_encoder(self, serial):
        """يختار مرمّز H.264 الحقيقي في عتاد الهاتف (الأسرع) بدل البرمجي البطيء."""
        _, o = run([self.scrcpy, "-s", serial, "--list-encoders"], timeout=25)
        best = None
        for line in o.splitlines():
            m = re.search(r"--video-codec=h264\s+--video-encoder='([^']+)'(.*)", line)
            if not m:
                continue
            name, rest = m.group(1), m.group(2).lower()
            if "(sw)" in rest:
                continue
            if "(hw)" in rest or not re.search(r"google|c2\.android|\.sw\.", name.lower()):
                best = best or name
        return best

    def toggle(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate(); return
        s = self.need()
        if not s: return
        base = [self.scrcpy, "-s", s, "--window-title", "جسر"]
        if self.size.get() != "الأصلية": base += ["--max-size", self.size.get()]
        base += ["--video-bit-rate", self.rate.get() + "M", "--max-fps", self.fps.get(), "--stay-awake"]
        if self.v_noaudio.get(): base.append("--no-audio")
        if self.v_off.get(): base.append("--turn-screen-off")
        if self.v_rec.get():
            f = out_dir("Videos") / time.strftime("jisr_%Y%m%d_%H%M%S.mp4")
            base.append(f"--record={f}"); self.log(f"التسجيل إلى: {f}")
        hw, low = self.v_hw.get(), self.v_low.get()
        self.btn.state(["disabled"]); self.btn.configure(text="… جارٍ التشغيل")
        self.status.configure(text="جارٍ التحضير…")
        self.bg(lambda: self._launch(s, base, hw, low))

    def _launch(self, s, base, hw, low):
        flags = NOWIN | (getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0) if low else 0)
        tries = [base]
        if hw:
            enc = self.hw_encoder(s)
            if enc:
                self.log(f"مرمّز الفيديو (عتاد): {enc}")
                tries = [base + ["--video-codec=h264", f"--video-encoder={enc}"], base]
        for a in tries:
            try:
                p = subprocess.Popen(a, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
            except Exception as e:
                self.log(f"فشل التشغيل: {e}"); break
            self.proc = p
            def reader(p=p):
                for line in p.stdout:
                    self.log(line.decode("utf-8", "replace").rstrip())
            self.bg(reader)
            time.sleep(4)
            if p.poll() is None:
                def ok():
                    self.btn.state(["!disabled"]); self.btn.configure(text="■  أوقف العرض")
                    self.status.configure(text="● جارٍ العرض")
                self.after(0, ok)
                return
            if a is not tries[-1]:
                self.log("فشل المرمّز الخاص، أعيد المحاولة بالإعداد الافتراضي…")
        self.proc = None
        def fail():
            self.btn.state(["!disabled"]); self.btn.configure(text="▶  ابدأ عرض الشاشة")
            self.status.configure(text="جاهز")
        self.after(0, fail)

    def _poll(self):
        if self.proc and self.proc.poll() is not None:
            self.proc = None
            self.btn.configure(text="▶  ابدأ عرض الشاشة"); self.status.configure(text="جاهز")
        self.after(1000, self._poll)

    def diag(self):
        if not self.adb:
            return self.log("⚠ adb غير موجود.")
        s = self.serial()
        def job():
            self.log("— تشخيص —")
            _, v = run([self.adb, "version"])
            self.log(v.strip().splitlines()[0] if v.strip() else "adb لا يعمل")
            run([self.adb, "kill-server"]); run([self.adb, "start-server"])
            _, mm = run([self.adb, "mdns", "check"]); self.log("mdns: " + (mm.strip().splitlines()[0] if mm.strip() else "غير متاح"))
            _, o = run([self.adb, "devices", "-l"])
            self.log(o.strip())
            if os.name == "nt":
                ps = ("Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match "
                      "'ADB|Android|MTP|Composite|Unisoc|Spreadtrum|MediaTek|itel|Transsion' } | "
                      "ForEach-Object { $_.Status + ' | ' + $_.FriendlyName }")
                _, p = run(["powershell", "-NoProfile", "-Command", ps], timeout=25)
                self.log("أجهزة USB التي يراها ويندوز:\n" + (p.strip() or "لا شيء — الكابل للشحن فقط أو الهاتف على وضع الشحن."))
            if s:
                _, enc = run([self.scrcpy, "-s", s, "--list-encoders"], timeout=25)
                ls = [l.strip() for l in enc.splitlines() if "h264" in l.lower()]
                self.log("مرمّزات الفيديو في هاتفك:\n" + ("\n".join(ls[:6]) or "غير معروفة"))
            self.log("انتهى. صوّر هذا السجل وأرسله للمطور إن استمرت المشكلة.")
        self.bg(job)

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
