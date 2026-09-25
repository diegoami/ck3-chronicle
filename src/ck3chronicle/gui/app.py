"""The window: Tk widgets only. What they do is :mod:`ck3chronicle.gui.session`."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .. import __version__
from . import paths, session

TICKED, UNTICKED = "☑", "☐"
POLL_MS = 100


class App:
    def __init__(self, root: tk.Tk, settings: session.Settings | None = None):
        self.root = root
        self.settings = settings or session.Settings.load()
        self.job: session.BuildJob | None = None
        self.rows: dict[str, session.Playthrough] = {}
        self.scan_notice = ""  #: what the folder scan had to say
        #: the player asked to quit during a build: close once the worker has stopped
        self.closing = False
        root.title("CK3 Chronicle")
        root.minsize(640, 520)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._menu()
        self._widgets()
        self.saves_var.set(str(self.settings.saves))
        self.output_var.set(str(self.settings.output))
        self.rescan()
        self._refresh_buttons()

    # ---------------------------------------------------------------- layout

    def _menu(self) -> None:
        bar = tk.Menu(self.root)
        file = tk.Menu(bar, tearoff=False)
        file.add_command(label="Clear cache…", command=self.clear_cache)
        file.add_command(label="Show last build's log", command=self.show_log)
        file.add_separator()
        file.add_command(label="Quit", command=self.close)
        bar.add_cascade(label="File", menu=file)
        about = tk.Menu(bar, tearoff=False)
        about.add_command(label="About", command=lambda: messagebox.showinfo(
            "About", f"CK3 Chronicle {__version__}\nChronicles of Crusader Kings III playthroughs."))
        bar.add_cascade(label="Help", menu=about)
        self.root.config(menu=bar)

    def _widgets(self) -> None:
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        self.saves_var, self.output_var = tk.StringVar(), tk.StringVar()
        for row, (label, var, pick) in enumerate((
            ("Saves", self.saves_var, self.pick_saves),
            ("Output", self.output_var, self.pick_output),
        )):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=2)
            entry = ttk.Entry(frame, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", pady=2)
            ttk.Button(frame, text="Browse…", command=pick).grid(row=row, column=2, padx=(6, 0), pady=2)
        self.saves_entry = frame.grid_slaves(row=0, column=1)[0]
        self.saves_entry.bind("<Return>", lambda _e: self.rescan())
        self.saves_entry.bind("<FocusOut>", lambda _e: self.rescan_if_changed())

        ttk.Label(frame, text="Playthroughs found").grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 2))
        columns = ("build", "character", "version", "saves", "years")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=6, selectmode="browse")
        for column, heading, width, anchor in (
            ("build", "", 30, "center"), ("character", "Played character", 260, "w"),
            ("version", "Version", 80, "w"), ("saves", "Saves", 60, "e"), ("years", "Years", 110, "w"),
        ):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor=anchor, stretch=column == "character")
        self.tree.grid(row=3, column=0, columnspan=3, sticky="nsew")
        self.tree.bind("<ButtonRelease-1>", self.toggle)
        self.tree.bind("<space>", self.toggle)
        frame.rowconfigure(3, weight=1)

        self.notice = ttk.Label(frame, text="", foreground="#8a4b00", wraplength=600, justify="left")
        self.notice.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        self.build_button = ttk.Button(buttons, text="Build", command=self.build)
        self.build_button.pack(side="left")
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel)
        self.cancel_button.pack(side="left", padx=6)
        self.open_button = ttk.Button(buttons, text="Open chronicle", command=self.open)
        self.open_button.pack(side="right")

        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=6, column=0, columnspan=3, sticky="ew")
        self.status = ttk.Label(frame, text="")
        self.status.grid(row=7, column=0, columnspan=3, sticky="w")

        self.log = ScrolledText(frame, height=10, state="disabled", wrap="word")
        self.log.tag_configure("warning", foreground="#a33")
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        frame.rowconfigure(8, weight=1)

    # ---------------------------------------------------------------- folders and rows

    def pick_saves(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self._existing(self.saves_var.get()), title="The folder with your saves")
        if chosen:
            self.saves_var.set(chosen)
            self.rescan()

    def pick_output(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self._existing(self.output_var.get()), title="Where the chronicles go")
        if chosen:
            self.output_var.set(chosen)
            self._refresh_buttons()

    @staticmethod
    def _existing(path: str) -> str:
        p = Path(path)
        while not p.is_dir() and p != p.parent:
            p = p.parent
        return str(p)

    def rescan_if_changed(self) -> None:
        if Path(self.saves_var.get()) != self.settings.saves:
            self.rescan()

    def rescan(self) -> None:
        self.settings.saves = Path(self.saves_var.get())
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        self.scan_notice = ""
        try:
            found, skipped = session.scan_folder(self.settings.saves)
        except session.FolderProblem as problem:
            self.scan_notice = str(problem)
            self._refresh_buttons()
            return
        for row in found:
            self.rows[row.key] = row
            mark = UNTICKED if row.key in self.settings.unticked else TICKED
            self.tree.insert("", "end", iid=row.key, values=(mark, row.character, row.version, row.saves, row.years))
        self.scan_notice = (
            f"{len(skipped)} file(s) skipped, not readable as saves: "
            + ", ".join(name for name, _ in skipped[:5]) + ("…" if len(skipped) > 5 else "")
        ) if skipped else ""
        self._refresh_buttons()

    def toggle(self, event=None) -> None:
        if self.job is not None:
            return
        key = self.tree.focus()
        if not key:
            return
        if key in self.settings.unticked:
            self.settings.unticked.discard(key)
        else:
            self.settings.unticked.add(key)
        values = list(self.tree.item(key, "values"))
        values[0] = UNTICKED if key in self.settings.unticked else TICKED
        self.tree.item(key, values=values)
        self._refresh_buttons()

    def chosen(self) -> list[str]:
        return [key for key in self.rows if key not in self.settings.unticked]

    # ---------------------------------------------------------------- building

    def build(self) -> None:
        out = Path(self.output_var.get())
        self.settings.output = out
        warning = session.output_warning(out)
        if warning and (warning.endswith("?") and not messagebox.askyesno("Output folder", warning, parent=self.root)):
            return
        if warning and not warning.endswith("?"):
            messagebox.showerror("Output folder", warning, parent=self.root)
            return
        try:
            config = session.desktop_config()
        except session.FolderProblem as problem:
            messagebox.showerror("Settings", str(problem), parent=self.root)
            return
        self.settings.save()
        self._clear_log()
        self.progress.config(value=0, maximum=1)
        self.status.config(text="Starting…")
        self.job = session.BuildJob(self.settings.saves, out, self.chosen(), config, paths.log_path()).start()
        self._refresh_buttons()
        self.root.after(POLL_MS, self.poll)

    def poll(self) -> None:
        job = self.job
        if job is None:
            return
        try:
            # the job's last event ends it (handle() lets go of it): stop there,
            # never ask a finished job for more (#18)
            while self.job is job:
                self.handle(job.events.get_nowait())
        except queue.Empty:
            pass
        if self.job is job:
            self.root.after(POLL_MS, self.poll)

    def handle(self, event: tuple) -> None:
        kind = event[0]
        if kind == "progress":
            p = event[1]
            self.progress.config(maximum=max(p.steps, 1), value=p.step)
            what = {"read": "read", "write": "wrote", "start": "", "done": ""}.get(p.stage, "")
            self.status.config(text=f"{what} {p.message} ({p.step}/{p.steps})".strip())
        elif kind == "log":
            self._append(event[2], warning=event[1] >= logging.WARNING)
        else:
            self.job = None
            if self.closing:
                self._finish_close()
                return
            if kind == "done":
                result = event[1]
                skipped = f", {len(result.skipped)} file(s) skipped" if result.skipped else ""
                self.status.config(text=f"Done: {len(result.chronicles)} chronicle(s), {result.pages} pages{skipped}.")
            elif kind == "cancelled":
                self.status.config(text=event[1])
            else:
                self.status.config(text="The build did not finish.")
                messagebox.showerror("Build", event[1], parent=self.root)
            self._refresh_buttons()

    def cancel(self) -> None:
        if self.job is not None:
            self.job.cancel.set()
            self.status.config(text="Stopping after the current save…")

    def open(self) -> None:
        session.open_chronicle(self.output_var.get())

    def close(self) -> None:
        if self.closing:
            return
        if self.job is not None:
            if not messagebox.askyesno("Quit", "A build is running. Stop it and quit?", parent=self.root):
                return
            # stop the way Cancel does, and close only once the worker has: a
            # chronicle being written is finished, never cut off (#21)
            self.closing = True
            self.job.cancel.set()
            self.status.config(text="Stopping after the current save, then closing…")
            self._refresh_buttons()
            return
        self._finish_close()

    def _finish_close(self) -> None:
        self.settings.saves = Path(self.saves_var.get())
        self.settings.output = Path(self.output_var.get())
        self.settings.save()
        self.root.destroy()

    # ---------------------------------------------------------------- the rest

    def clear_cache(self) -> None:
        try:
            config = session.desktop_config()
        except session.FolderProblem as problem:
            messagebox.showerror("Settings", str(problem), parent=self.root)
            return
        size = session.cache_size(config)
        if messagebox.askyesno(
            "Clear cache",
            f"The cache holds {size / 1e6:.0f} MB in {config.cache}. It only makes builds faster:"
            " the next build reads every save again. Clear it?",
            parent=self.root,
        ):
            session.clear_cache(config)

    def show_log(self) -> None:
        log = paths.log_path()
        if log.is_file():
            session.webbrowser.open(log.resolve().as_uri())
        else:
            messagebox.showinfo("Log", "No build has run yet.", parent=self.root)

    def _refresh_buttons(self) -> None:
        running = self.job is not None
        self.build_button.config(state="disabled" if running or not self.chosen() else "normal")
        self.cancel_button.config(state="normal" if running and not self.closing else "disabled")
        self.open_button.config(state="normal" if not running and session.has_chronicle(self.output_var.get()) else "disabled")
        # why Build is off when the folder is fine but nothing is ticked (#20)
        nothing = "Tick at least one playthrough to build it." if self.rows and not self.chosen() else ""
        self.notice.config(text="\n".join(part for part in (self.scan_notice, nothing) if part))

    def _append(self, text: str, warning: bool = False) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", ("warning",) if warning else ())
        self.log.see("end")
        self.log.config(state="disabled")

    def _clear_log(self) -> None:
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


def run() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0
