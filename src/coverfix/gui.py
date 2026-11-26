"""Desktop window: pick a folder, see every track as a row, fix covers."""

from __future__ import annotations

import io
import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageOps, ImageTk

from .core import UnsupportedFormat, clean_file, inspect_file
from .model import FIELD_LABELS, FileReport, Picture, make_picture

AUDIO_SUFFIXES = {".mp3", ".flac", ".m4a", ".m4b", ".mp4", ".ogg", ".oga", ".opus", ".aac"}

BG = "#0B0B0D"
SURFACE = "#141417"
SURFACE_2 = "#1B1B20"
HOVER = "#17171C"
SELECTED = "#27272F"
TEXT = "#F2F2F5"
MUTED = "#9A9AA3"
DIM = "#6E6E78"
ACCENT = "#8B5CF6"
ACCENT_HOVER = "#7C3AED"
BORDER = "#26262D"

ROW_HEIGHT = 64
THUMB_SIZE = 48
DETAIL_COVER = 170

FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_HEAD = ("Segoe UI", 15, "bold")
FONT_MONO = ("Consolas", 9)


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _cover_image(data: bytes | None, size: int, radius: int = 8, background: str = SURFACE) -> Image.Image:
    if data:
        try:
            image = Image.open(io.BytesIO(data)).convert("RGB")
            image = ImageOps.fit(image, (size, size), Image.LANCZOS)
        except Exception:
            image = None
    else:
        image = None

    if image is None:
        image = Image.new("RGB", (size, size), "#232330")
        draw = ImageDraw.Draw(image)
        centre = size / 2
        for radius_ring, colour in ((size * 0.34, "#34344a"), (size * 0.16, "#3d3d58"), (size * 0.05, "#4a4a6a")):
            draw.ellipse(
                (centre - radius_ring, centre - radius_ring, centre + radius_ring, centre + radius_ring),
                outline=colour,
                width=max(2, size // 32),
            )

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    canvas = Image.new("RGB", (size, size), background)
    canvas.paste(image, (0, 0), mask)
    return canvas


def _ellipsize(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _duration(seconds: float | int | None) -> str:
    if not seconds:
        return ""
    total = max(1, int(round(float(seconds))))
    return f"{total // 60}:{total % 60:02d}"


class SlimScrollbar(tk.Canvas):
    """A quiet scrollbar that matches the dark surface instead of the OS theme."""

    def __init__(self, master: tk.Misc, command) -> None:  # noqa: ANN001
        super().__init__(master, width=9, bg=BG, highlightthickness=0, bd=0)
        self._command = command
        self._first = 0.0
        self._last = 1.0
        self.bind("<Configure>", lambda _event: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)

    def set(self, first: str, last: str) -> None:
        self._first = float(first)
        self._last = float(last)
        self._redraw()

    def _redraw(self) -> None:
        self.delete("thumb")
        height = self.winfo_height()
        span = self._last - self._first
        if height <= 1 or span >= 0.999:
            return
        size = max(30.0, span * height)
        top = min(self._first * height, height - size)
        self.create_rectangle(2, top, 7, top + size, fill=SURFACE_2, outline="", tags="thumb")

    def _on_press(self, event: tk.Event) -> None:  # noqa: ANN001
        height = self.winfo_height()
        if height > 1:
            self._command("moveto", min(max(event.y / height, 0.0), 1.0))

    def _on_drag(self, event: tk.Event) -> None:  # noqa: ANN001
        self._on_press(event)


class TrackList(tk.Canvas):
    """Canvas-drawn list: one row per track with cover, title, artist, length."""

    def __init__(self, master: tk.Misc, on_select) -> None:  # noqa: ANN001
        super().__init__(master, bg=BG, highlightthickness=0, bd=0, takefocus=True)
        self.on_select = on_select
        self.reports: list[FileReport] = []
        self._photos: list[ImageTk.PhotoImage] = []
        self._rows: list[dict] = []
        self._hover = -1
        self._selection: set[int] = set()
        self._anchor = -1
        self._placeholder = ImageTk.PhotoImage(_cover_image(None, THUMB_SIZE, 8, BG))

        self.bind("<Configure>", lambda _event: self._layout())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _event: self._set_hover(-1))
        self.bind("<Button-1>", self._on_click)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Control-a>", self._select_all)
        self.bind("<Control-A>", self._select_all)

    # ------------------------------------------------------------------ data
    def set_reports(self, reports: list[FileReport]) -> None:
        self.reports = reports
        self._selection = {0} if reports else set()
        self._anchor = 0 if reports else -1
        self._hover = -1
        self._build()

    def select(self, index: int) -> None:
        if not 0 <= index < len(self.reports):
            return
        self._selection = {index}
        self._anchor = index
        self._refresh_states()
        self.on_select([self.reports[index]])

    def select_paths(self, paths: set[Path], notify: bool = True) -> None:
        self._selection = {index for index, report in enumerate(self.reports) if report.path in paths}
        self._anchor = min(self._selection) if self._selection else -1
        self._refresh_states()
        if notify and self._selection:
            self.on_select([self.reports[index] for index in sorted(self._selection)])

    def selected_reports(self) -> list[FileReport]:
        return [self.reports[index] for index in sorted(self._selection)]

    def _select_all(self, _event=None) -> str:  # noqa: ANN001
        if self.reports:
            self._selection = set(range(len(self.reports)))
            self._anchor = 0
            self._refresh_states()
            self.on_select(self.selected_reports())
        return "break"

    # --------------------------------------------------------------- drawing
    def _build(self) -> None:
        self.delete("all")
        self._rows.clear()
        self._photos.clear()

        if not self.reports:
            self._draw_empty()
            self.configure(scrollregion=(0, 0, 0, 0))
            return

        width = max(self.winfo_width(), 200)
        for index, report in enumerate(self.reports):
            top = index * ROW_HEIGHT
            hover = self.create_rectangle(0, top, width, top + ROW_HEIGHT, fill=HOVER, outline="")
            selected = self.create_rectangle(0, top, width, top + ROW_HEIGHT, fill=SELECTED, outline="")
            photo = self._photo_for(report)
            image = self.create_image(16, top + (ROW_HEIGHT - THUMB_SIZE) // 2, image=photo, anchor="nw")
            title = self.create_text(
                16 + THUMB_SIZE + 14,
                top + 20,
                text="",
                anchor="w",
                fill=TEXT,
                font=FONT_TITLE,
            )
            artist = self.create_text(
                16 + THUMB_SIZE + 14,
                top + 41,
                text="",
                anchor="w",
                fill=MUTED,
                font=FONT_SMALL,
            )
            length = self.create_text(width - 18, top + ROW_HEIGHT // 2, text="", anchor="e", fill=DIM, font=FONT_MONO)
            badge = self.create_text(width - 66, top + ROW_HEIGHT // 2, text="", anchor="e", fill=ACCENT, font=FONT_SMALL)
            self._rows.append(
                {
                    "hover": hover,
                    "selected": selected,
                    "image": image,
                    "title": title,
                    "artist": artist,
                    "length": length,
                    "badge": badge,
                }
            )

        self.configure(scrollregion=(0, 0, width, len(self.reports) * ROW_HEIGHT))
        self._layout()
        self._refresh_states()

    def _draw_empty(self) -> None:
        width = max(self.winfo_width(), 400)
        height = max(self.winfo_height(), 300)
        self.create_text(
            width // 2,
            height // 2 - 16,
            text="Откройте папку с треками",
            fill=MUTED,
            font=("Segoe UI", 13),
        )
        self.create_text(
            width // 2,
            height // 2 + 14,
            text="Ctrl+O или кнопка «Открыть папку», либо перетащите файлы в окно",
            fill=DIM,
            font=FONT_SMALL,
        )

    def _photo_for(self, report: FileReport) -> ImageTk.PhotoImage:
        cover = report.front_cover
        if cover is None:
            self._photos.append(self._placeholder)
            return self._placeholder
        photo = ImageTk.PhotoImage(_cover_image(cover.data, THUMB_SIZE, 8, BG))
        self._photos.append(photo)
        return photo

    def _layout(self) -> None:
        width = max(self.winfo_width(), 200)
        limit = max(18, int((width - THUMB_SIZE - 130) / 7.2))
        for report, row in zip(self.reports, self._rows):
            title = report.fields.get("title") or report.path.stem
            artist = report.fields.get("artist") or "—"
            self.itemconfigure(row["title"], text=_ellipsize(title, limit))
            self.itemconfigure(row["artist"], text=_ellipsize(artist, limit))
            self.itemconfigure(row["length"], text=_duration(report.audio.get("duration")))
            covers = len(report.pictures)
            self.itemconfigure(row["badge"], text=f"{covers}" if covers != 1 else "")
            self.coords(row["selected"], 0, 0, width, 0)
            self.coords(row["hover"], 0, 0, width, 0)
        for index, row in enumerate(self._rows):
            top = index * ROW_HEIGHT
            self.coords(row["hover"], 0, top, width, top + ROW_HEIGHT)
            self.coords(row["selected"], 0, top, width, top + ROW_HEIGHT)
            self.coords(row["image"], 16, top + (ROW_HEIGHT - THUMB_SIZE) // 2)
            self.coords(row["title"], 16 + THUMB_SIZE + 14, top + 20)
            self.coords(row["artist"], 16 + THUMB_SIZE + 14, top + 41)
            self.coords(row["length"], width - 18, top + ROW_HEIGHT // 2)
            self.coords(row["badge"], width - 62, top + ROW_HEIGHT // 2)

    def _refresh_states(self) -> None:
        for index, row in enumerate(self._rows):
            selected = index in self._selection
            self.itemconfigure(
                row["hover"], state="normal" if index == self._hover and not selected else "hidden"
            )
            self.itemconfigure(row["selected"], state="normal" if selected else "hidden")
            self.tag_raise(row["hover"])
            self.tag_raise(row["selected"])
            for key in ("image", "title", "artist", "length", "badge"):
                self.tag_raise(row[key])

    # ----------------------------------------------------------------- events
    def _index_at(self, y: int) -> int:
        if not self.reports:
            return -1
        index = int(y // ROW_HEIGHT)
        return index if 0 <= index < len(self.reports) else -1

    def _on_motion(self, event: tk.Event) -> None:  # noqa: ANN001
        index = self._index_at(int(self.canvasy(event.y)))
        self._set_hover(index)
        self.configure(cursor="hand2" if index >= 0 else "")

    def _set_hover(self, index: int) -> None:
        if index == self._hover:
            return
        self._hover = index
        self._refresh_states()

    def _on_click(self, event: tk.Event) -> None:  # noqa: ANN001
        index = self._index_at(int(self.canvasy(event.y)))
        if index < 0:
            return
        self.focus_set()
        control = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)

        if shift and self._anchor >= 0:
            low, high = sorted((self._anchor, index))
            self._selection = set(range(low, high + 1))
        elif control:
            if index in self._selection:
                self._selection.discard(index)
            else:
                self._selection.add(index)
            self._anchor = index
            if not self._selection:
                self._selection = {index}
        else:
            self._selection = {index}
            self._anchor = index

        self._refresh_states()
        self.on_select(self.selected_reports())

    def _on_wheel(self, event: tk.Event) -> None:  # noqa: ANN001
        self.yview_scroll(int(-event.delta / 120), "units")


class App:
    def __init__(self, root: tk.Misc, dnd_available: bool) -> None:
        self.root = root
        self.dnd_available = dnd_available
        self.reports: dict[Path, FileReport] = {}
        self.order: list[Path] = []
        self.current: FileReport | None = None
        self.selection: list[FileReport] = []
        self._baseline: dict[str, str | None] = {}
        self.chosen: Picture | None = None
        self._detail_photo: ImageTk.PhotoImage | None = None
        self._cover_photos: list[ImageTk.PhotoImage] = []

        if isinstance(root, tk.Tk):
            root.title("CoverFix")
            root.geometry("1180x760")
            root.minsize(920, 600)
            root.configure(bg=BG)

        self._build_header()
        self._build_body()
        self._build_status()

        if isinstance(root, tk.Tk):
            root.bind("<Control-o>", lambda _event: self.open_folder())
            root.bind("<Control-O>", lambda _event: self.open_folder())
        if dnd_available:
            self._enable_drop()

    # ---------------------------------------------------------------- chrome
    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=18, pady=(16, 6))

        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        tk.Label(brand, text="CoverFix", bg=BG, fg=TEXT, font=FONT_HEAD).pack(anchor="w")
        tk.Label(
            brand,
            text="обложки и теги без сюрпризов",
            bg=BG,
            fg=DIM,
            font=FONT_SMALL,
        ).pack(anchor="w")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        search = tk.Entry(
            header,
            textvariable=self.search_var,
            bg=SURFACE_2,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=FONT_BODY,
            width=18,
        )
        search.pack(side="right", ipady=6, padx=(8, 0))
        tk.Label(header, text="Поиск", bg=BG, fg=DIM, font=FONT_SMALL).pack(side="right", padx=(0, 6))

        self._button(header, "Добавить файлы", self.add_files_dialog, accent=False).pack(side="right", padx=(0, 6))
        self._button(header, "Открыть папку", self.open_folder, accent=True).pack(side="right", padx=(0, 6))

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=18, pady=(8, 0))

    def _button(self, parent: tk.Misc, text: str, command, accent: bool = False) -> tk.Button:  # noqa: ANN001
        background = ACCENT if accent else SURFACE_2
        active = ACCENT_HOVER if accent else HOVER
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=TEXT if accent else "#D6D6DD",
            activebackground=active,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=14,
            pady=6,
            font=FONT_BODY,
            cursor="hand2",
        )
        button.bind("<Enter>", lambda _event: button.configure(bg=active))
        button.bind("<Leave>", lambda _event: button.configure(bg=background))
        return button

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(10, 0))

        list_frame = tk.Frame(body, bg=BG)
        list_frame.pack(side="left", fill="both", expand=True)

        self.track_list = TrackList(list_frame, self._on_track_selected)
        scrollbar = SlimScrollbar(list_frame, self.track_list.yview)
        self.track_list.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(6, 0))
        self.track_list.pack(side="left", fill="both", expand=True)

        self._build_details(body)

    def _build_details(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=SURFACE, width=380)
        panel.pack(side="right", fill="y", padx=(14, 0))
        panel.pack_propagate(False)

        actions = tk.Frame(panel, bg=SURFACE)
        actions.pack(side="bottom", fill="x", padx=16, pady=(10, 12))
        self.write_button = self._button(actions, "Записать", self.apply_current, accent=True)
        self.write_button.pack(side="left")
        self._button(actions, "Записать все", self.apply_all).pack(side="left", padx=(6, 0))
        self.backup_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            actions,
            text="Бэкап",
            variable=self.backup_var,
            bg=SURFACE,
            fg=MUTED,
            activebackground=SURFACE,
            activeforeground=TEXT,
            selectcolor=SURFACE_2,
            font=FONT_SMALL,
            bd=0,
            highlightthickness=0,
        ).pack(side="right")

        self.detail_canvas = tk.Canvas(panel, bg=SURFACE, highlightthickness=0, bd=0)
        self.detail_canvas.pack(fill="both", expand=True)
        inner = tk.Frame(self.detail_canvas, bg=SURFACE)
        self._detail_window = self.detail_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda _event: self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all")),
        )
        self.detail_canvas.bind(
            "<Configure>",
            lambda event: self.detail_canvas.itemconfigure(self._detail_window, width=event.width),
        )
        self.detail_canvas.bind("<MouseWheel>", self._on_detail_wheel)

        self.detail_title = tk.Label(
            inner, text="Ничего не выбрано", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold"), anchor="w"
        )
        self.detail_title.pack(fill="x", padx=16, pady=(10, 2))
        self.detail_sub = tk.Label(inner, text="", bg=SURFACE, fg=DIM, font=FONT_SMALL, anchor="w")
        self.detail_sub.pack(fill="x", padx=16)

        self.detail_cover = tk.Label(inner, bg=SURFACE, bd=0)
        self.detail_cover.pack(pady=(8, 4))

        self.covers_row = tk.Frame(inner, bg=SURFACE)
        self.covers_row.pack(fill="x", padx=16)

        buttons = tk.Frame(inner, bg=SURFACE)
        buttons.pack(fill="x", padx=16, pady=(6, 0))
        self._button(buttons, "Вложить картинку", self.choose_cover).pack(side="left")
        self._button(buttons, "Без обложки", self.clear_cover).pack(side="left", padx=(6, 0))

        fields = tk.Frame(inner, bg=SURFACE)
        fields.pack(fill="x", padx=16, pady=(8, 0))
        self.vars: dict[str, tk.StringVar] = {}
        for index, (name, label) in enumerate(FIELD_LABELS.items()):
            row, column = divmod(index, 2)
            cell = tk.Frame(fields, bg=SURFACE)
            cell.grid(row=row, column=column, sticky="ew", padx=(0, 8), pady=3)
            tk.Label(cell, text=label, bg=SURFACE, fg=MUTED, font=FONT_SMALL, anchor="w").pack(fill="x")
            variable = tk.StringVar()
            self.vars[name] = variable
            entry = tk.Entry(
                cell,
                textvariable=variable,
                bg=SURFACE_2,
                fg=TEXT,
                insertbackground=TEXT,
                relief="flat",
                font=FONT_BODY,
                highlightthickness=1,
                highlightbackground=SURFACE_2,
                highlightcolor=ACCENT,
            )
            entry.pack(fill="x", ipady=3)
        fields.columnconfigure(0, weight=1)
        fields.columnconfigure(1, weight=1)

        self.warning_label = tk.Label(
            inner,
            text="",
            bg=SURFACE,
            fg="#E0A458",
            font=FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=330,
        )
        self._warning_packed = False

        self.multi_hint = tk.Label(
            inner,
            text="",
            bg=SURFACE,
            fg=DIM,
            font=FONT_SMALL,
            anchor="w",
            justify="left",
            wraplength=330,
        )
        self._hint_packed = False

        self._bind_wheel(inner)

    def _on_detail_wheel(self, event: tk.Event) -> str:  # noqa: ANN001
        self.detail_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _bind_wheel(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_detail_wheel)
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _build_status(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=18, pady=(8, 10))
        self.status = tk.StringVar(value="Готово")
        tk.Label(bar, textvariable=self.status, bg=BG, fg=DIM, font=FONT_SMALL, anchor="w").pack(side="left")
        self.count_label = tk.Label(bar, text="", bg=BG, fg=DIM, font=FONT_SMALL, anchor="e")
        self.count_label.pack(side="right")
        self.log_label = tk.Label(bar, text="", bg=BG, fg=MUTED, font=FONT_SMALL, anchor="e")
        self.log_label.pack(side="right", padx=(0, 16))

    # ----------------------------------------------------------------- data
    def open_folder(self) -> None:
        folder = filedialog.askdirectory(title="Папка с треками")
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path) -> None:
        folder = Path(folder)
        paths = sorted(
            path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES
        )
        if not paths:
            messagebox.showinfo("CoverFix", "В этой папке нет аудиофайлов.")
            return
        self._load(paths, replace=True)

    def add_files_dialog(self) -> None:
        names = filedialog.askopenfilenames(
            title="Аудиофайлы",
            filetypes=[("Аудио", " ".join(f"*{suffix}" for suffix in sorted(AUDIO_SUFFIXES))), ("Все файлы", "*.*")],
        )
        self.add_paths([Path(name) for name in names])

    def add_paths(self, paths: list[Path]) -> None:
        expanded: list[Path] = []
        for path in paths:
            path = Path(path)
            if path.is_dir():
                expanded.extend(
                    sorted(
                        child
                        for child in path.rglob("*")
                        if child.is_file() and child.suffix.lower() in AUDIO_SUFFIXES
                    )
                )
            elif path.suffix.lower() in AUDIO_SUFFIXES:
                expanded.append(path)
        self._load(expanded, replace=False)

    def _load(self, paths: list[Path], replace: bool) -> None:
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        if replace:
            self.order.clear()
            self.reports.clear()
        failures = 0
        for path in paths:
            resolved = path.resolve()
            if resolved in self.reports:
                continue
            try:
                self.reports[resolved] = inspect_file(resolved)
                self.order.append(resolved)
            except Exception:
                failures += 1
        self.root.configure(cursor="")
        self._apply_filter()
        self.status.set(
            f"Загружено треков: {len(self.order)}" + (f", ошибок: {failures}" if failures else "")
        )
        if self.track_list.reports:
            self.track_list.select(0)

    def _apply_filter(self) -> None:
        query = self.search_var.get().strip().lower()
        reports = []
        for path in self.order:
            report = self.reports.get(path)
            if report is None:
                continue
            if query:
                haystack = " ".join(
                    [report.fields.get("title", ""), report.fields.get("artist", ""), path.name]
                ).lower()
                if query not in haystack:
                    continue
            reports.append(report)
        self.track_list.set_reports(reports)
        self.count_label.configure(text=f"{len(reports)} из {len(self.order)}" if query else f"{len(reports)} треков")

    # --------------------------------------------------------------- actions
    def _enable_drop(self) -> None:
        from tkinterdnd2 import DND_FILES

        for widget in (self.root, self.track_list):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event) -> None:  # noqa: ANN001 - tkinter event
        self.add_paths([Path(item) for item in self.root.tk.splitlist(event.data)])

    def _on_track_selected(self, reports: list[FileReport]) -> None:
        if not reports:
            return
        self.selection = reports
        self.current = reports[0]
        single = len(reports) == 1

        self.chosen = next((report.front_cover for report in reports if report.front_cover), None)
        self._baseline = {}
        mixed = 0
        for name, variable in self.vars.items():
            values = {report.fields.get(name, "").strip() for report in reports}
            if len(values) == 1:
                value = next(iter(values))
                self._baseline[name] = value
                variable.set(value)
            else:
                mixed += 1
                self._baseline[name] = None
                variable.set("")

        if single:
            report = reports[0]
            title = report.fields.get("title") or report.path.stem
            artist = report.fields.get("artist") or "—"
            self.detail_title.configure(text=_ellipsize(title, 34))
            self.detail_sub.configure(
                text=f"{_ellipsize(artist, 30)} · {report.container.upper()} · {_duration(report.audio.get('duration'))}"
            )
            self._show_cover(self.chosen)
            self._show_cover_choices(report)
            warnings = report.warnings
            self.status.set(str(report.path))
        else:
            distinct_covers = len({picture.data for picture in (r.front_cover for r in reports) if picture})
            self.detail_title.configure(text=f"Выбрано треков: {len(reports)}")
            subtitle = "изменённые поля применятся ко всем"
            if distinct_covers > 1:
                subtitle += " · обложки различаются"
            self.detail_sub.configure(text=subtitle)
            self._show_cover(self.chosen)
            for child in self.covers_row.winfo_children():
                child.destroy()
            tk.Label(
                self.covers_row,
                text=f"Обложка будет вложена во все {len(reports)}",
                bg=SURFACE,
                fg=DIM,
                font=FONT_SMALL,
                anchor="w",
            ).pack(fill="x")
            warnings = []
            self.status.set(f"Выбрано треков: {len(reports)}")

        self.write_button.configure(text=f"Записать ({len(reports)})" if not single else "Записать")

        self.multi_hint.configure(
            text="Пустое поле означает разные значения. Заполните только то, что нужно "
            "проставить всем — остальное не изменится."
            if not single and mixed
            else ""
        )
        if not single and mixed and not self._hint_packed:
            self.multi_hint.pack(fill="x", padx=16, pady=(6, 0), before=self.warning_label)
            self._hint_packed = True
        elif (single or not mixed) and self._hint_packed:
            self.multi_hint.pack_forget()
            self._hint_packed = False

        self.warning_label.configure(text="")
        if self._warning_packed:
            self.warning_label.pack_forget()
            self._warning_packed = False
        self.warning_label.configure(text="\n".join(warnings[:2]))
        if warnings:
            self.warning_label.pack(fill="x", padx=16, pady=(8, 14))
            self._warning_packed = True

    def _show_cover(self, picture: Picture | None) -> None:
        image = _cover_image(picture.data if picture else None, DETAIL_COVER, 14, SURFACE)
        self._detail_photo = ImageTk.PhotoImage(image)
        self.detail_cover.configure(image=self._detail_photo)

    def _show_cover_choices(self, report: FileReport) -> None:
        for child in self.covers_row.winfo_children():
            child.destroy()
        self._cover_photos.clear()

        for picture in report.pictures[:8]:
            photo = ImageTk.PhotoImage(_cover_image(picture.data, 42, 6, SURFACE))
            self._cover_photos.append(photo)
            frame = tk.Frame(self.covers_row, bg=ACCENT if picture is self.chosen else SURFACE_2, padx=2, pady=2)
            frame.pack(side="left", padx=(0, 6))
            label = tk.Label(frame, image=photo, bg=SURFACE, bd=0, cursor="hand2")
            label.pack()
            label.bind("<Button-1>", lambda _event, chosen=picture: self._pick_cover(chosen))
        self._bind_wheel(self.covers_row)

    def _pick_cover(self, picture: Picture) -> None:
        self.chosen = picture
        self._show_cover(picture)
        if len(self.selection) == 1 and self.current is not None:
            for child in self.covers_row.winfo_children():
                child.destroy()
            self._show_cover_choices(self.current)
        self.status.set(f"Выбрана обложка: {picture.type_name}, {picture.resolution}")

    def choose_cover(self) -> None:
        name = filedialog.askopenfilename(
            title="Картинка обложки",
            filetypes=[("Изображения", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Все файлы", "*.*")],
        )
        if not name:
            return
        try:
            data = Path(name).read_bytes()
            self.chosen = make_picture(0, data, type=3, desc="Cover", source="file")
        except Exception as exc:
            self.status.set(f"Не удалось прочитать картинку: {exc}")
            return
        self._show_cover(self.chosen)
        self.status.set(f"Внешняя обложка: {Path(name).name}")

    def clear_cover(self) -> None:
        self.chosen = None
        self._show_cover(None)
        self.status.set("Файл будет записан без обложки")

    def apply_current(self) -> None:
        paths = [report.path for report in self.selection]
        if not paths:
            messagebox.showinfo("CoverFix", "Выберите треки в списке.")
            return
        self._apply(paths)

    def _changes(self) -> dict[str, str]:
        """Fields the user actually changed; everything else keeps each file's value."""
        changes: dict[str, str] = {}
        for name, variable in self.vars.items():
            value = variable.get().strip()
            baseline = self._baseline.get(name)
            if baseline is None:
                if value:
                    changes[name] = value
            elif value != baseline:
                changes[name] = value
        return changes

    def apply_all(self) -> None:
        if not self.order:
            messagebox.showinfo("CoverFix", "Список пуст.")
            return
        if not messagebox.askyesno(
            "CoverFix",
            f"Применить выбранную обложку и поля ко всем трекам ({len(self.order)})?\n"
            "Перед записью создаются копии .bak.",
        ):
            return
        self._apply(list(self.order))

    def _apply(self, paths: list[Path]) -> None:
        changes = self._changes()
        cover = self.chosen
        selected_paths = [report.path for report in self.selection]
        ok = 0
        for path in paths:
            report = self.reports.get(path)
            metadata = dict(report.fields) if report is not None else {}
            metadata.update(changes)
            try:
                after = clean_file(path, keep=cover, metadata=metadata, backup=self.backup_var.get())
            except Exception as exc:
                self.log_label.configure(text=f"Ошибка: {path.name}")
                self.status.set(f"{path.name}: {exc}")
                traceback.print_exc(limit=1)
                continue
            self.reports[path] = after
            ok += 1
        if ok:
            self._apply_filter()
            self.log_label.configure(text=f"Записано: {ok}")
            self.status.set(f"Записано файлов: {ok} из {len(paths)}")
            if self.current is not None:
                for index, report in enumerate(self.track_list.reports):
                    if report.path == self.current.path:
                        self.track_list.select(index)
                        break
        else:
            self.status.set(f"Ничего не записано: {len(paths)} ошибок")


def create_root():
    try:
        from tkinterdnd2 import TkinterDnD

        return TkinterDnD.Tk(), True
    except Exception:
        return tk.Tk(), False


def _icon_file() -> Path | None:
    roots = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    roots.append(Path(__file__).resolve().parents[2])
    for root in roots:
        candidate = root / "assets" / "app.ico"
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    _enable_dpi_awareness()
    root, dnd = create_root()
    icon = _icon_file()
    if icon is not None:
        try:
            root.iconbitmap(default=str(icon))
        except Exception:
            pass
    app = App(root, dnd)
    for argument in sys.argv[1:]:
        candidate = Path(argument)
        if candidate.is_dir():
            app.load_folder(candidate)
        elif candidate.is_file():
            app.add_paths([candidate])
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
