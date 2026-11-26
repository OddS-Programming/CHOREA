"""Desktop window: drop files, see every cover, keep one."""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk

from PIL import Image, ImageTk

from .core import UnsupportedFormat, clean_file, inspect_file
from .model import FIELD_LABELS, FileReport, Picture, make_picture

PREVIEW_SIZE = (240, 240)
AUDIO_SUFFIXES = {".mp3", ".flac", ".m4a", ".m4b", ".mp4", ".ogg", ".oga", ".opus", ".aac"}


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class App:
    def __init__(self, root: Tk, dnd_available: bool) -> None:
        self.root = root
        self.dnd_available = dnd_available
        self.reports: dict[Path, FileReport] = {}
        self.pictures: list[Picture] = []
        self.chosen: Picture | None = None
        self._photo: ImageTk.PhotoImage | None = None

        self.root.title("CoverFix — одна обложка, чистые теги")
        self.root.geometry("1000x680")
        self.root.minsize(860, 560)

        self._build_toolbar()
        self._build_body()
        self._build_log()
        self._build_status()

        if dnd_available:
            self._enable_drop()

    # ---------------------------------------------------------------- layout
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(10, 10, 10, 4))
        bar.pack(fill=X)
        ttk.Button(bar, text="Добавить файлы…", command=self.add_files_dialog).pack(side=LEFT)
        ttk.Button(bar, text="Обновить", command=self.refresh_current).pack(side=LEFT, padx=(6, 0))
        ttk.Button(bar, text="Убрать из списка", command=self.remove_selected).pack(side=LEFT, padx=(6, 0))

        ttk.Separator(bar, orient="vertical").pack(side=LEFT, fill=Y, padx=12)

        ttk.Button(bar, text="Очистить и записать", command=self.apply_selected).pack(side=LEFT)
        ttk.Button(bar, text="Применить ко всем", command=self.apply_all).pack(side=LEFT, padx=(6, 0))

        self.backup_var = BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Бэкап .bak", variable=self.backup_var).pack(side=RIGHT)

    def _build_body(self) -> None:
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill=BOTH, expand=True, padx=10, pady=6)

        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        columns = ("container", "covers", "tags")
        self.file_tree = ttk.Treeview(left, columns=columns, show="tree headings", selectmode="extended")
        self.file_tree.heading("#0", text="Файл")
        self.file_tree.heading("container", text="Формат")
        self.file_tree.heading("covers", text="Обложек")
        self.file_tree.heading("tags", text="Теги")
        self.file_tree.column("#0", width=260, anchor="w")
        self.file_tree.column("container", width=70, anchor="center")
        self.file_tree.column("covers", width=70, anchor="center")
        self.file_tree.column("tags", width=190, anchor="w")
        self.file_tree.pack(side=LEFT, fill=BOTH, expand=True)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.file_tree.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self.file_tree.configure(yscrollcommand=scroll.set)
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_selected)

        right = ttk.Frame(paned)
        paned.add(right, weight=2)

        preview_row = ttk.Frame(right)
        preview_row.pack(fill=X)
        self.preview = ttk.Label(preview_row, text="обложки нет", anchor="center", width=34, relief="groove")
        self.preview.pack(side=LEFT, padx=(0, 10), ipady=6)

        picture_frame = ttk.LabelFrame(preview_row, text="Обложки в файле", padding=6)
        picture_frame.pack(side=LEFT, fill=BOTH, expand=True)
        self.picture_tree = ttk.Treeview(
            picture_frame, columns=("type", "mime", "size"), show="headings", height=6, selectmode="browse"
        )
        self.picture_tree.heading("type", text="Тип")
        self.picture_tree.heading("mime", text="Формат")
        self.picture_tree.heading("size", text="Размер")
        self.picture_tree.column("type", width=150, anchor="w")
        self.picture_tree.column("mime", width=110, anchor="w")
        self.picture_tree.column("size", width=120, anchor="w")
        self.picture_tree.pack(fill=BOTH, expand=True)
        self.picture_tree.bind("<<TreeviewSelect>>", self._on_picture_selected)

        picture_buttons = ttk.Frame(picture_frame)
        picture_buttons.pack(fill=X, pady=(6, 0))
        ttk.Button(picture_buttons, text="Вложить картинку…", command=self.choose_cover).pack(side=LEFT)
        ttk.Button(picture_buttons, text="Без обложки", command=self.clear_cover).pack(side=LEFT, padx=(6, 0))

        self._build_metadata(right)

    def _build_metadata(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Метаданные (применяются к записываемым файлам)", padding=8)
        frame.pack(fill=BOTH, expand=True, pady=(10, 0))

        self.vars: dict[str, StringVar] = {}
        for index, (name, label) in enumerate(FIELD_LABELS.items()):
            row, column = divmod(index, 2)
            cell = ttk.Frame(frame)
            cell.grid(row=row, column=column, sticky="ew", padx=6, pady=3)
            ttk.Label(cell, text=label, width=18).pack(side=LEFT)
            variable = StringVar()
            self.vars[name] = variable
            ttk.Entry(cell, textvariable=variable).pack(side=LEFT, fill=X, expand=True)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _build_log(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Журнал", padding=4)
        frame.pack(fill=BOTH, expand=False, padx=10, pady=(0, 4))
        self.log_text = ttk.Treeview(frame, columns=("message",), show="headings", height=6)
        self.log_text.heading("message", text="Что сделано")
        self.log_text.column("message", width=900, anchor="w")
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=scroll.set)

    def _build_status(self) -> None:
        self.status = StringVar(value="Перетащите файлы в окно или нажмите «Добавить файлы…»")
        ttk.Label(self.root, textvariable=self.status, anchor="w", padding=(10, 2, 10, 8)).pack(fill=X)

    def _enable_drop(self) -> None:
        from tkinterdnd2 import DND_FILES

        for widget in (self.root, self.file_tree):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

    # ----------------------------------------------------------------- events
    def _on_drop(self, event) -> None:  # noqa: ANN001 - tkinter event
        paths = [Path(item) for item in self.root.tk.splitlist(event.data)]
        self.add_paths(paths)

    def _on_file_selected(self, _event=None) -> None:  # noqa: ANN001
        selection = self.file_tree.selection()
        if not selection:
            return
        path = Path(selection[0])
        report = self.reports.get(path)
        if report is None:
            try:
                report = inspect_file(path)
            except Exception as exc:
                self.log(f"ОШИБКА {path.name}: {exc}")
                return
            self.reports[path] = report
        self._show_report(path, report)

    def _on_picture_selected(self, _event=None) -> None:  # noqa: ANN001
        selection = self.picture_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if 0 <= index < len(self.pictures):
            self.chosen = self.pictures[index]
            self._set_preview(self.chosen)

    # ------------------------------------------------------------- operations
    def add_files_dialog(self) -> None:
        names = filedialog.askopenfilenames(
            title="Аудиофайлы",
            filetypes=[
                ("Аудио", "*.mp3 *.flac *.m4a *.m4b *.mp4 *.ogg *.oga *.opus *.aac"),
                ("Все файлы", "*.*"),
            ],
        )
        self.add_paths([Path(name) for name in names])

    def add_paths(self, paths: list[Path]) -> None:
        added = 0
        for path in paths:
            if path.is_dir():
                for child in sorted(path.iterdir()):
                    if child.suffix.lower() in AUDIO_SUFFIXES:
                        added += self._add_one(child)
                continue
            added += self._add_one(path)
        if added:
            self.status.set(f"Добавлено файлов: {added}")
        if added and not self.file_tree.selection():
            first = self.file_tree.get_children()
            if first:
                self.file_tree.selection_set(first[0])
                self._on_file_selected()

    def _add_one(self, path: Path) -> int:
        path = path.resolve()
        if path in self.reports:
            return 0
        try:
            report = inspect_file(path)
        except (FileNotFoundError, UnsupportedFormat) as exc:
            self.log(f"ПРОПУСК {path.name}: {exc}")
            return 0
        except Exception as exc:
            self.log(f"ОШИБКА {path.name}: {exc}")
            return 0
        self.reports[path] = report
        self.file_tree.insert(
            "",
            END,
            iid=str(path),
            text=path.name,
            values=(report.container, len(report.pictures), ", ".join(report.tag_versions)),
        )
        return 1

    def remove_selected(self) -> None:
        for item in self.file_tree.selection():
            path = Path(item)
            self.reports.pop(path, None)
            self.file_tree.delete(item)

    def refresh_current(self) -> None:
        selection = self.file_tree.selection()
        if not selection:
            return
        path = Path(selection[0])
        try:
            report = inspect_file(path)
        except Exception as exc:
            self.log(f"ОШИБКА {path.name}: {exc}")
            return
        self.reports[path] = report
        self.file_tree.item(
            str(path),
            values=(report.container, len(report.pictures), ", ".join(report.tag_versions)),
        )
        self._show_report(path, report)

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
            self.log(f"ОШИБКА чтения картинки: {exc}")
            return
        self._set_preview(self.chosen)
        self.status.set(f"Выбрана внешняя картинка: {Path(name).name} ({self.chosen.size} Б)")

    def clear_cover(self) -> None:
        self.chosen = None
        self.picture_tree.selection_remove(self.picture_tree.selection())
        self._set_preview(None)
        self.status.set("Запись пройдёт без обложки")

    def apply_selected(self) -> None:
        selection = [Path(item) for item in self.file_tree.selection()]
        if not selection:
            messagebox.showinfo("CoverFix", "Выберите файлы в списке слева.")
            return
        self._apply(selection)

    def apply_all(self) -> None:
        paths = [Path(item) for item in self.file_tree.get_children()]
        if not paths:
            messagebox.showinfo("CoverFix", "Список пуст.")
            return
        if not messagebox.askyesno(
            "CoverFix",
            f"Применить выбранную обложку и поля ко всем файлам ({len(paths)})?\n"
            "Создаются резервные копии .bak.",
        ):
            return
        self._apply(paths)

    def _apply(self, paths: list[Path]) -> None:
        metadata = {name: variable.get().strip() for name, variable in self.vars.items()}
        cover = self.chosen
        ok = 0
        for path in paths:
            try:
                after = clean_file(path, keep=cover, metadata=metadata, backup=self.backup_var.get())
            except Exception as exc:
                self.log(f"ОШИБКА {path.name}: {exc}")
                self.log(traceback.format_exc(limit=1))
                continue
            ok += 1
            self.reports[path] = after
            if self.file_tree.exists(str(path)):
                self.file_tree.item(
                    str(path),
                    values=(after.container, len(after.pictures), ", ".join(after.tag_versions)),
                )
            self.log(
                f"OK {path.name}: обложек {len(after.pictures)}, теги {', '.join(after.tag_versions) or 'нет'}"
            )
        self.status.set(f"Записано файлов: {ok} из {len(paths)}")
        current = self.file_tree.selection()
        if current:
            self._show_report(Path(current[0]), self.reports[Path(current[0])])

    # ------------------------------------------------------------------ view
    def _show_report(self, path: Path, report: FileReport) -> None:
        for name, variable in self.vars.items():
            variable.set(report.fields.get(name, ""))

        self.pictures = report.pictures
        self.picture_tree.delete(*self.picture_tree.get_children())
        for picture in report.pictures:
            self.picture_tree.insert(
                "",
                END,
                iid=str(picture.index),
                values=(picture.type_name, picture.mime, f"{picture.resolution}, {picture.size} Б"),
            )

        self.chosen = report.front_cover
        self._set_preview(self.chosen)
        if report.pictures:
            self.picture_tree.selection_set(str(self.chosen.index) if self.chosen else "0")

        versions = ", ".join(report.tag_versions) or "нет"
        self.status.set(
            f"{path.name}: {report.container}, теги {versions}, обложек {len(report.pictures)}"
        )
        for warning in report.warnings:
            self.log(f"! {path.name}: {warning}")

    def _set_preview(self, picture: Picture | None) -> None:
        if picture is None:
            self._photo = None
            self.preview.configure(image="", text="обложки нет")
            return
        try:
            image = Image.open(io.BytesIO(picture.data))
            image.thumbnail(PREVIEW_SIZE)
            photo = ImageTk.PhotoImage(image)
        except Exception:
            self._photo = None
            self.preview.configure(image="", text="превью недоступно")
            return
        self._photo = photo
        self.preview.configure(image=photo, text="")

    def log(self, message: str) -> None:
        self.log_text.insert("", END, values=(message,))
        children = self.log_text.get_children()
        if children:
            self.log_text.see(children[-1])


def create_root() -> tuple[Tk, bool]:
    try:
        from tkinterdnd2 import TkinterDnD

        return TkinterDnD.Tk(), True
    except Exception:
        return Tk(), False


def main() -> int:
    _enable_dpi_awareness()
    root, dnd = create_root()
    App(root, dnd)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
