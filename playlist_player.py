"""
Tunebox - Mini Music Playlist Manager (Spotify-style desktop app)

Requirements:   pip install pygame
Optional:       pip install mutagen      (more accurate song durations)
Run:            python playlist_player.py

Each playlist is a doubly linked list of songs, so next/previous
playback just follows the links. Data is saved to tunebox_data.json.
"""

import array
import json
import math
import os
import random
import sys
import wave
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pygame
except ImportError:
    pygame = None
try:
    import mutagen
except ImportError:
    mutagen = None

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunebox_data.json")
AUDIO_TYPES = [("Audio files", "*.mp3 *.wav *.ogg *.flac"), ("All files", "*.*")]


# ======================= Data structure: doubly linked list =======================
class Song:
    def __init__(self, path, title, artist, duration):
        self.path = path
        self.title = title
        self.artist = artist
        self.duration = duration  # seconds (0 if unknown)
        self.prev = None
        self.next = None

    def to_dict(self):
        return {"path": self.path, "title": self.title, "artist": self.artist, "duration": self.duration}


class Playlist:
    def __init__(self, name):
        self.name = name
        self.head = None
        self.tail = None
        self.size = 0

    def songs(self):
        node = self.head
        while node:
            yield node
            node = node.next

    def to_array(self):
        return list(self.songs())

    def add(self, song):
        if any(s.path == song.path for s in self.songs()):
            return False  # no duplicates
        if not self.head:
            self.head = self.tail = song
        else:
            song.prev = self.tail
            self.tail.next = song
            self.tail = song
        self.size += 1
        return True

    def remove(self, node):
        if node.prev:
            node.prev.next = node.next
        else:
            self.head = node.next
        if node.next:
            node.next.prev = node.prev
        else:
            self.tail = node.prev
        node.prev = node.next = None
        self.size -= 1

    def rebuild(self, order):
        self.head = self.tail = None
        self.size = 0
        for s in order:
            s.prev = s.next = None
            self.add(s)

    def sort_by(self, key):
        keys = {
            "Title": lambda s: s.title.lower(),
            "Artist": lambda s: s.artist.lower(),
            "Duration": lambda s: s.duration,
        }
        if key in keys:
            self.rebuild(sorted(self.songs(), key=keys[key]))

    def swap(self, i, j):
        a = self.to_array()
        if 0 <= i < len(a) and 0 <= j < len(a):
            a[i], a[j] = a[j], a[i]
            self.rebuild(a)

    def total_duration(self):
        return sum(s.duration for s in self.songs())

    def to_dict(self):
        return {"name": self.name, "songs": [s.to_dict() for s in self.songs()]}


def fmt(seconds):
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"


# ============================= Built-in demo songs =============================
# Public-domain melodies, synthesized into WAV files so the app works out of the box.
DEMO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_songs")
SEMITONES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
             "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

# Format: "NOTE" or "NOTE:beats"  (default 1 beat), e.g. "C4 D4:2 E4:0.5"
DEMO_SONGS = [
    {"title": "Twinkle Twinkle Little Star", "artist": "Traditional", "bpm": 100, "melody":
        "C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2 "
        "G4 G4 F4 F4 E4 E4 D4:2 G4 G4 F4 F4 E4 E4 D4:2 "
        "C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2"},
    {"title": "Ode to Joy", "artist": "Beethoven", "bpm": 110, "melody":
        "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4:1.5 D4:0.5 D4:2 "
        "E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:0.5 C4:2"},
    {"title": "Frere Jacques", "artist": "Traditional", "bpm": 110, "melody":
        "C4 D4 E4 C4 C4 D4 E4 C4 E4 F4 G4:2 E4 F4 G4:2 "
        "G4:0.5 A4:0.5 G4:0.5 F4:0.5 E4 C4 G4:0.5 A4:0.5 G4:0.5 F4:0.5 E4 C4 "
        "C4 G3 C4:2 C4 G3 C4:2"},
    {"title": "Jingle Bells", "artist": "Traditional", "bpm": 130, "melody":
        "E4 E4 E4:2 E4 E4 E4:2 E4 G4 C4:1.5 D4:0.5 E4:4 "
        "F4 F4 F4:1.5 F4:0.5 F4 E4 E4 E4:0.5 E4:0.5 G4 G4 F4 D4 C4:4"},
    {"title": "Fur Elise (opening)", "artist": "Beethoven", "bpm": 120, "melody":
        "E5:0.5 D#5:0.5 E5:0.5 D#5:0.5 E5:0.5 B4:0.5 D5:0.5 C5:0.5 A4:1.5 "
        "C4:0.5 E4:0.5 A4:0.5 B4:1.5 E4:0.5 G#4:0.5 B4:0.5 C5:1.5 "
        "E4:0.5 E5:0.5 D#5:0.5 E5:0.5 D#5:0.5 E5:0.5 B4:0.5 D5:0.5 C5:0.5 A4:1.5 "
        "C4:0.5 E4:0.5 A4:0.5 B4:1.5 E4:0.5 C5:0.5 B4:0.5 A4:2"},
]


def note_freq(name):
    midi = 12 * (int(name[-1]) + 1) + SEMITONES[name[:-1]]
    return 440.0 * 2 ** ((midi - 69) / 12)


def parse_melody(text):
    notes = []
    for tok in text.split():
        name, _, beats = tok.partition(":")
        notes.append((name, float(beats) if beats else 1.0))
    return notes


def write_wav(path, melody, bpm, rate=22050):
    """Synthesize the melody into a mono 16-bit WAV file. Returns duration in seconds."""
    beat = 60.0 / bpm
    samples = array.array("h")
    for name, beats in melody:
        freq = note_freq(name)
        n = int(rate * beat * beats)
        fade = int(rate * 0.02)
        for k in range(n):
            t = k / rate
            env = min(1.0, k / (rate * 0.01)) * (0.35 + 0.65 * math.exp(-3.0 * k / n))
            if k > n - fade:
                env *= max(0.0, (n - k) / fade)
            v = (math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(4 * math.pi * freq * t)
                 + 0.1 * math.sin(6 * math.pi * freq * t))
            samples.append(int(v / 1.4 * env * 0.6 * 32767))
    if sys.byteorder == "big":
        samples.byteswap()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return int(round(len(samples) / rate))


def make_demo_files(folder=DEMO_DIR):
    """Create the demo WAV files (if missing). Returns [(path, title, artist, duration), ...]."""
    os.makedirs(folder, exist_ok=True)
    result = []
    for d in DEMO_SONGS:
        path = os.path.join(folder, f"{d['artist']} - {d['title']}.wav")
        if os.path.exists(path):
            with wave.open(path, "rb") as w:
                duration = int(round(w.getnframes() / w.getframerate()))
        else:
            duration = write_wav(path, parse_melody(d["melody"]), d["bpm"])
        result.append((path, d["title"], d["artist"], duration))
    return result


# ============================== GUI (Tkinter + pygame) ==============================
BG, SIDE, PANEL, HOVER = "#09090d", "#101018", "#16161f", "#22222f"
TEXT, MUTED, ACCENT, ACCENT2 = "#f3f2fa", "#9b99b0", "#ff4d8d", "#7c5cff"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Tunebox - Mini Music Player")
        root.geometry("1020x640")
        root.minsize(860, 540)
        root.configure(bg=BG)
        pygame.mixer.init()

        self.playlists = []
        self.cur = None            # playlist being viewed
        self.now_pl = None         # playlist being played
        self.now = None            # song node being played
        self.playing = False
        self.paused = False
        self.offset = 0.0          # seconds, used after seeking
        self.shuffle = False
        self.repeat = 0            # 0 off, 1 playlist, 2 song
        self.dragging = False
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *a: self.refresh_songs())

        self.load()
        self.build_ui()
        self.refresh_playlists()
        self.refresh_songs()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<space>", self.on_space)
        self.tick()

    # ---------------------------- persistence ----------------------------
    def load(self):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            for pl in raw.get("playlists", []):
                p = Playlist(pl["name"])
                for s in pl["songs"]:
                    p.add(Song(s["path"], s["title"], s["artist"], int(s.get("duration", 0))))
                self.playlists.append(p)
            sel = raw.get("selected")
            self.cur = next((p for p in self.playlists if p.name == sel), None)
        except (OSError, ValueError, KeyError):
            self.playlists = []
        if not self.cur and self.playlists:
            self.cur = self.playlists[0]

    def save(self):
        data = {"playlists": [p.to_dict() for p in self.playlists],
                "selected": self.cur.name if self.cur else None}
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    # ------------------------------- layout -------------------------------
    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=30, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=PANEL, foreground=MUTED, borderwidth=0,
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", HOVER)], foreground=[("selected", TEXT)])
        style.map("Treeview.Heading", background=[("active", PANEL)])
        style.configure("TCombobox", fieldbackground=BG, background=HOVER, foreground=TEXT)

        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # ---- sidebar ----
        side = tk.Frame(self.root, bg=SIDE, width=250)
        side.grid(row=0, column=0, sticky="ns", padx=(8, 4), pady=8)
        side.grid_propagate(False)
        tk.Label(side, text="♫ Tunebox", bg=SIDE, fg=ACCENT, font=("Segoe UI", 18, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(16, 14))
        tk.Label(side, text="YOUR LIBRARY", bg=SIDE, fg=MUTED, font=("Segoe UI", 8, "bold"),
                 anchor="w").pack(fill="x", padx=14)
        row = tk.Frame(side, bg=SIDE)
        row.pack(fill="x", padx=12, pady=8)
        self.new_name = tk.Entry(row, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                                 font=("Segoe UI", 10))
        self.new_name.pack(side="left", fill="x", expand=True, ipady=5)
        self.new_name.bind("<Return>", lambda e: self.create_playlist())
        self.flat_button(row, "+", self.create_playlist, ACCENT2, width=3).pack(side="left", padx=(6, 0))

        self.pl_box = tk.Listbox(side, bg=SIDE, fg=TEXT, selectbackground=HOVER, selectforeground=TEXT,
                                 relief="flat", highlightthickness=0, activestyle="none",
                                 font=("Segoe UI", 11), exportselection=False)
        self.pl_box.pack(fill="both", expand=True, padx=12, pady=4)
        self.pl_box.bind("<<ListboxSelect>>", self.on_pick_playlist)
        self.flat_button(side, "Delete playlist", self.delete_playlist, HOVER, fg="#ff7a93").pack(
            fill="x", padx=12, pady=(4, 12))

        # ---- main ----
        main = tk.Frame(self.root, bg=PANEL)
        main.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        main.rowconfigure(3, weight=1)
        main.columnconfigure(0, weight=1)

        head = tk.Frame(main, bg=PANEL)
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 6))
        self.hdr_name = tk.Label(head, text="Welcome to Tunebox", bg=PANEL, fg=TEXT,
                                 font=("Segoe UI", 26, "bold"), anchor="w")
        self.hdr_name.pack(fill="x")
        self.hdr_meta = tk.Label(head, text="Create a playlist on the left to get started.",
                                 bg=PANEL, fg=MUTED, anchor="w", font=("Segoe UI", 10))
        self.hdr_meta.pack(fill="x")

        acts = tk.Frame(main, bg=PANEL)
        acts.grid(row=1, column=0, sticky="ew", padx=24, pady=6)
        self.flat_button(acts, "▶  Play", self.header_play, ACCENT, fg="white").pack(side="left", padx=(0, 8))
        self.flat_button(acts, "＋ Add songs", self.add_songs, HOVER).pack(side="left", padx=4)
        self.flat_button(acts, "✨ Demo songs", self.add_demo_songs, HOVER).pack(side="left", padx=4)
        self.flat_button(acts, "↑", lambda: self.move(-1), HOVER, width=3).pack(side="left", padx=4)
        self.flat_button(acts, "↓", lambda: self.move(1), HOVER, width=3).pack(side="left", padx=4)
        self.flat_button(acts, "Remove", self.remove_selected, HOVER, fg="#ff7a93").pack(side="left", padx=4)

        tools = tk.Frame(main, bg=PANEL)
        tools.grid(row=2, column=0, sticky="ew", padx=24, pady=(4, 8))
        tk.Entry(tools, textvariable=self.search, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=("Segoe UI", 10), width=30).pack(side="left", ipady=5)
        tk.Label(tools, text="  🔍 search     Sort:", bg=PANEL, fg=MUTED).pack(side="left")
        self.sort_box = ttk.Combobox(tools, values=["Title", "Artist", "Duration"], state="readonly", width=10)
        self.sort_box.pack(side="left", padx=6)
        self.sort_box.bind("<<ComboboxSelected>>", self.on_sort)

        tree_frame = tk.Frame(main, bg=PANEL)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 12))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("n", "title", "artist", "time"),
                                 show="headings", selectmode="browse")
        for col, text, w, anchor in (("n", "#", 40, "center"), ("title", "TITLE", 320, "w"),
                                     ("artist", "ARTIST", 200, "w"), ("time", "TIME", 70, "e")):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=w, anchor=anchor, stretch=(col == "title"))
        self.tree.tag_configure("playing", foreground=ACCENT)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self.on_double_click)

        # ---- player bar ----
        bar = tk.Frame(self.root, bg=SIDE, height=92)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        bar.grid_propagate(False)
        bar.columnconfigure(0, weight=1, uniform="p")
        bar.columnconfigure(1, weight=2, uniform="p")
        bar.columnconfigure(2, weight=1, uniform="p")

        info = tk.Frame(bar, bg=SIDE)
        info.grid(row=0, column=0, sticky="w", padx=16)
        self.np_title = tk.Label(info, text="Nothing playing", bg=SIDE, fg=TEXT, anchor="w",
                                 font=("Segoe UI", 11, "bold"))
        self.np_title.pack(fill="x")
        self.np_artist = tk.Label(info, text="Pick a song to start", bg=SIDE, fg=MUTED, anchor="w")
        self.np_artist.pack(fill="x")

        center = tk.Frame(bar, bg=SIDE)
        center.grid(row=0, column=1, sticky="ew")
        ctrl = tk.Frame(center, bg=SIDE)
        ctrl.pack(pady=(10, 0))
        self.b_shuffle = self.icon_button(ctrl, "🔀", self.toggle_shuffle)
        self.b_shuffle.pack(side="left", padx=8)
        self.icon_button(ctrl, "⏮", self.prev_track).pack(side="left", padx=8)
        self.b_play = tk.Button(ctrl, text="▶", command=self.toggle_play, bg=TEXT, fg="black", relief="flat",
                                font=("Segoe UI", 12, "bold"), width=3, cursor="hand2", activebackground="white")
        self.b_play.pack(side="left", padx=8)
        self.icon_button(ctrl, "⏭", self.next_track).pack(side="left", padx=8)
        self.b_repeat = self.icon_button(ctrl, "🔁", self.toggle_repeat)
        self.b_repeat.pack(side="left", padx=8)

        seek_row = tk.Frame(center, bg=SIDE)
        seek_row.pack(fill="x", padx=20, pady=(2, 0))
        self.t_cur = tk.Label(seek_row, text="0:00", bg=SIDE, fg=MUTED, width=5)
        self.t_cur.pack(side="left")
        self.seek = tk.Scale(seek_row, from_=0, to=1000, orient="horizontal", showvalue=0, bg=SIDE,
                             troughcolor=HOVER, highlightthickness=0, bd=0, sliderrelief="flat",
                             activebackground=ACCENT, length=300)
        self.seek.pack(side="left", fill="x", expand=True)
        self.seek.bind("<ButtonPress-1>", lambda e: setattr(self, "dragging", True))
        self.seek.bind("<ButtonRelease-1>", self.on_seek_release)
        self.t_tot = tk.Label(seek_row, text="0:00", bg=SIDE, fg=MUTED, width=5)
        self.t_tot.pack(side="left")

        vol = tk.Frame(bar, bg=SIDE)
        vol.grid(row=0, column=2, sticky="e", padx=16)
        tk.Label(vol, text="🔊", bg=SIDE, fg=MUTED).pack(side="left")
        self.vol = tk.Scale(vol, from_=0, to=100, orient="horizontal", showvalue=0, bg=SIDE,
                            troughcolor=HOVER, highlightthickness=0, bd=0, sliderrelief="flat",
                            activebackground=ACCENT, length=120,
                            command=lambda v: pygame.mixer.music.set_volume(int(v) / 100))
        self.vol.set(80)
        self.vol.pack(side="left", padx=6)
        pygame.mixer.music.set_volume(0.8)

    def flat_button(self, parent, text, cmd, bg, fg=TEXT, width=None):
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat", cursor="hand2",
                      font=("Segoe UI", 10), padx=12, pady=4, activebackground=HOVER, activeforeground=fg)
        if width:
            b.config(width=width)
        return b

    def icon_button(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=SIDE, fg=MUTED, relief="flat", bd=0,
                         font=("Segoe UI", 13), cursor="hand2", activebackground=SIDE, activeforeground=TEXT)

    # ---------------------------- refreshing ----------------------------
    def refresh_playlists(self):
        self.pl_box.delete(0, "end")
        for i, p in enumerate(self.playlists):
            self.pl_box.insert("end", f"  {p.name}   ({p.size})")
            if p is self.cur:
                self.pl_box.selection_set(i)

    def refresh_songs(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        p = self.cur
        if not p:
            self.hdr_name.config(text="Welcome to Tunebox")
            self.hdr_meta.config(text="Create a playlist on the left to get started.")
            return
        total = p.total_duration()
        self.hdr_name.config(text=p.name)
        self.hdr_meta.config(text=f"{p.size} song{'s' if p.size != 1 else ''}  ·  "
                                  f"{total // 60} min {total % 60} sec")
        q = self.search.get().strip().lower()
        for i, s in enumerate(p.songs()):
            if q and q not in s.title.lower() and q not in s.artist.lower():
                continue
            is_now = s is self.now
            marker = ("⏸" if self.paused else "▶") if is_now else str(i + 1)
            self.tree.insert("", "end", iid=str(i), values=(marker, s.title, s.artist, fmt(s.duration)),
                             tags=("playing",) if is_now else ())

    def refresh_player(self):
        n = self.now
        self.np_title.config(text=n.title if n else "Nothing playing")
        self.np_artist.config(text=n.artist if n else "Pick a song to start")
        self.b_play.config(text="⏸" if (self.playing and not self.paused) else "▶")
        if not n:
            self.seek.set(0)
            self.t_cur.config(text="0:00")
            self.t_tot.config(text="0:00")
        else:
            self.t_tot.config(text=fmt(n.duration) if n.duration else "--:--")

    # --------------------------- playlist actions ---------------------------
    def create_playlist(self):
        name = self.new_name.get().strip()
        if not name:
            return messagebox.showwarning("Tunebox", "Enter a playlist name.")
        if any(p.name.lower() == name.lower() for p in self.playlists):
            return messagebox.showwarning("Tunebox", "A playlist with that name already exists.")
        p = Playlist(name)
        self.playlists.append(p)
        self.cur = p
        self.new_name.delete(0, "end")
        self.save()
        self.refresh_playlists()
        self.refresh_songs()

    def delete_playlist(self):
        p = self.cur
        if not p or not messagebox.askyesno("Tunebox", f"Delete playlist '{p.name}'?"):
            return
        if self.now_pl is p:
            self.stop_all()
        self.playlists.remove(p)
        self.cur = self.playlists[0] if self.playlists else None
        self.save()
        self.refresh_playlists()
        self.refresh_songs()

    def on_pick_playlist(self, _event):
        sel = self.pl_box.curselection()
        if sel:
            self.cur = self.playlists[sel[0]]
            self.search.set("")
            self.save()
            self.refresh_songs()

    def get_duration(self, path):
        if mutagen:
            try:
                f = mutagen.File(path)
                if f and f.info and f.info.length:
                    return int(round(f.info.length))
            except Exception:
                pass
        try:
            return int(round(pygame.mixer.Sound(path).get_length()))
        except Exception:
            return 0

    def add_songs(self):
        if not self.cur:
            return messagebox.showinfo("Tunebox", "Create a playlist first.")
        paths = filedialog.askopenfilenames(title="Choose audio files", filetypes=AUDIO_TYPES)
        added = 0
        for path in paths:
            base = os.path.splitext(os.path.basename(path))[0]
            title, artist = base, "Unknown artist"
            if " - " in base:
                artist, title = [x.strip() for x in base.split(" - ", 1)]
            if self.cur.add(Song(path, title, artist, self.get_duration(path))):
                added += 1
        if paths and not added:
            messagebox.showinfo("Tunebox", "Those songs are already in this playlist.")
        self.save()
        self.refresh_playlists()
        self.refresh_songs()

    def add_demo_songs(self):
        if not self.cur:
            return messagebox.showinfo("Tunebox", "Create a playlist first.")
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            files = make_demo_files()
        except OSError as e:
            self.root.config(cursor="")
            return messagebox.showerror("Tunebox", f"Could not create demo songs:\n{e}")
        self.root.config(cursor="")
        added = sum(1 for path, title, artist, dur in files if self.cur.add(Song(path, title, artist, dur)))
        if not added:
            messagebox.showinfo("Tunebox", "The demo songs are already in this playlist.")
        self.save()
        self.refresh_playlists()
        self.refresh_songs()

    def selected_index(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def remove_selected(self):
        i = self.selected_index()
        if i is None or not self.cur:
            return
        node = self.cur.to_array()[i]
        if node is self.now:
            self.stop_all()
        self.cur.remove(node)
        self.save()
        self.refresh_playlists()
        self.refresh_songs()

    def move(self, d):
        i = self.selected_index()
        if i is None or not self.cur:
            return
        self.cur.swap(i, i + d)
        self.save()
        self.refresh_songs()
        j = i + d
        if self.tree.exists(str(j)):
            self.tree.selection_set(str(j))

    def on_sort(self, _event):
        if self.cur:
            self.cur.sort_by(self.sort_box.get())
            self.save()
            self.refresh_songs()

    # ------------------------------ playback ------------------------------
    def position(self):
        return self.offset + max(0, pygame.mixer.music.get_pos()) / 1000.0

    def play_node(self, pl, node):
        if not os.path.exists(node.path):
            return messagebox.showerror("Tunebox", f"File not found:\n{node.path}")
        try:
            pygame.mixer.music.load(node.path)
            pygame.mixer.music.play()
        except pygame.error as e:
            return messagebox.showerror("Tunebox", f"Cannot play this file:\n{e}")
        self.now_pl, self.now = pl, node
        self.offset = 0.0
        self.playing, self.paused = True, False
        self.refresh_player()
        self.refresh_songs()

    def stop_all(self):
        pygame.mixer.music.stop()
        if hasattr(pygame.mixer.music, "unload"):
            pygame.mixer.music.unload()
        self.now_pl = self.now = None
        self.playing = self.paused = False
        self.offset = 0.0
        self.refresh_player()
        self.refresh_songs()

    def header_play(self):
        if not self.cur or not self.cur.head:
            return messagebox.showinfo("Tunebox", "This playlist is empty. Add some songs first.")
        i = self.selected_index()
        if self.now_pl is self.cur and self.now and i is None:
            self.toggle_play()
        else:
            node = self.cur.to_array()[i] if i is not None else self.cur.head
            self.play_node(self.cur, node)

    def on_double_click(self, _event):
        i = self.selected_index()
        if i is not None and self.cur:
            self.play_node(self.cur, self.cur.to_array()[i])

    def toggle_play(self):
        if not self.now:
            if self.cur and self.cur.head:
                self.play_node(self.cur, self.cur.head)
            return
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
        else:
            pygame.mixer.music.pause()
            self.paused = True
        self.refresh_player()
        self.refresh_songs()

    def on_space(self, _event):
        if not isinstance(self.root.focus_get(), (tk.Entry, ttk.Combobox)):
            self.toggle_play()

    def pick_next(self, auto):
        pl, node = self.now_pl, self.now
        if not pl or not node or not pl.size:
            return None
        if self.shuffle and pl.size > 1:
            choices = [s for s in pl.songs() if s is not node]
            return random.choice(choices)
        if node.next:
            return node.next
        if not auto or self.repeat == 1:
            return pl.head
        return None

    def next_track(self):
        n = self.pick_next(False)
        if n:
            self.play_node(self.now_pl, n)

    def prev_track(self):
        if not self.now:
            return
        if self.position() > 3:
            self.seek_to(0)
        else:
            self.play_node(self.now_pl, self.now.prev or self.now_pl.tail)

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.b_shuffle.config(fg=ACCENT if self.shuffle else MUTED)

    def toggle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        self.b_repeat.config(text="🔂" if self.repeat == 2 else "🔁", fg=ACCENT if self.repeat else MUTED)

    def seek_to(self, pos):
        if not self.now:
            return
        try:
            pygame.mixer.music.play(start=pos)
            self.offset = pos
            if self.paused:
                pygame.mixer.music.pause()
        except pygame.error:
            pass

    def on_seek_release(self, _event):
        if self.now and self.now.duration:
            self.seek_to(self.seek.get() / 1000.0 * self.now.duration)
        self.dragging = False

    def on_end(self):
        if self.repeat == 2 and self.now:
            return self.play_node(self.now_pl, self.now)
        n = self.pick_next(True)
        if n:
            self.play_node(self.now_pl, n)
        else:
            self.playing = False
            self.paused = False
            self.refresh_player()
            self.refresh_songs()

    def tick(self):
        if self.playing and not self.paused:
            if not pygame.mixer.music.get_busy():
                self.on_end()
            elif not self.dragging and self.now:
                pos = self.position()
                if self.now.duration:
                    self.seek.set(min(1000, pos / self.now.duration * 1000))
                self.t_cur.config(text=fmt(pos))
        self.root.after(300, self.tick)

    def on_close(self):
        self.save()
        pygame.mixer.quit()
        self.root.destroy()


def main():
    if pygame is None:
        print("This app needs pygame. Install it with:  pip install pygame")
        return
    root = tk.Tk()
    try:
        App(root)
    except pygame.error as e:
        messagebox.showerror("Tunebox", f"Could not start the audio system:\n{e}")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
