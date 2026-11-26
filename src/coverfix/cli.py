"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import UnsupportedFormat, clean_file, inspect_file
from .model import FIELD_LABELS, FileReport, Picture, make_picture

METADATA_FLAGS = {
    "title": "название",
    "artist": "исполнитель",
    "album": "альбом",
    "album_artist": "исполнитель альбома",
    "track": "трек (3 или 3/12)",
    "disc": "диск (1 или 1/2)",
    "year": "год",
    "genre": "жанр",
}


def _format_audio(audio: dict) -> str:
    if not audio:
        return "не читается"
    parts = [
        f"{audio.get('duration', 0)} с",
        f"{audio.get('bitrate', 0) // 1000} kbps",
        f"{audio.get('sample_rate', 0)} Hz",
        f"{audio.get('channels', 0)} кан.",
    ]
    return ", ".join(parts)


def _format_report(report: FileReport) -> str:
    lines = [str(report.path)]
    lines.append(f"  контейнер : {report.container}")
    lines.append(f"  аудио     : {_format_audio(report.audio)}")
    lines.append(f"  теги      : {', '.join(report.tag_versions) or 'нет'}")
    lines.append(f"  обложки   : {len(report.pictures)}")
    for picture in report.pictures:
        lines.append(
            f"    [{picture.index}] {picture.type_name:<14} {picture.mime:<28} "
            f"{picture.resolution:<10} {picture.size:>8} Б  {picture.source}"
        )
    if report.fields:
        lines.append("  поля      : " + ", ".join(f"{name}={value}" for name, value in report.fields.items()))
    if report.warnings:
        lines.append("  предупреждения:")
        lines.extend(f"    - {warning}" for warning in report.warnings)
    return "\n".join(lines)


def _load_cover(path: Path) -> Picture:
    data = path.read_bytes()
    return make_picture(0, data, type=3, desc="Cover", source="file")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coverfix",
        description="Показывает все теги и все обложки в аудиофайле и пересобирает его с одной обложкой.",
    )
    parser.add_argument("--version", action="version", version="coverfix 1.0.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect = subparsers.add_parser("inspect", help="показать всё, что лежит в файле")
    inspect.add_argument("files", nargs="+", type=Path)
    inspect.add_argument("--json", action="store_true", help="машиночитаемый вывод")

    clean = subparsers.add_parser("clean", help="пересобрать файл: один набор тегов, одна обложка")
    clean.add_argument("file", type=Path)
    choice = clean.add_mutually_exclusive_group()
    choice.add_argument("--keep", type=int, metavar="N", help="индекс обложки, которую оставить")
    choice.add_argument("--no-cover", action="store_true", help="удалить все обложки")
    choice.add_argument("--cover", type=Path, metavar="PATH", help="вложить эту картинку")
    for name, description in METADATA_FLAGS.items():
        clean.add_argument(f"--{name.replace('_', '-')}", dest=name, help=description)
    clean.add_argument("--id3", type=int, choices=[3, 4], default=3, help="версия ID3v2 для mp3")
    clean.add_argument("--dry-run", action="store_true", help="показать, что будет сделано")
    clean.add_argument("--no-backup", action="store_true", help="не создавать .bak")
    return parser


def _cmd_inspect(args: argparse.Namespace) -> int:
    reports = []
    for path in args.files:
        try:
            reports.append(inspect_file(path))
        except (FileNotFoundError, UnsupportedFormat) as exc:
            print(f"ошибка: {exc}", file=sys.stderr)
            return 1
    if args.json:
        payload = [report.to_dict() for report in reports]
        print(json.dumps(payload[0] if len(payload) == 1 else payload, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(_format_report(report) for report in reports))
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    try:
        report = inspect_file(args.file)
    except (FileNotFoundError, UnsupportedFormat) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1

    if args.no_cover:
        keep = None
    elif args.cover is not None:
        if not args.cover.exists():
            print(f"ошибка: нет файла обложки {args.cover}", file=sys.stderr)
            return 1
        keep = _load_cover(args.cover)
    elif args.keep is not None:
        if not 0 <= args.keep < len(report.pictures):
            print(
                f"ошибка: индекс {args.keep} вне диапазона, в файле {len(report.pictures)} обложек",
                file=sys.stderr,
            )
            return 1
        keep = report.pictures[args.keep]
    else:
        keep = report.front_cover

    metadata = dict(report.fields)
    for name in METADATA_FLAGS:
        value = getattr(args, name)
        if value is not None:
            metadata[name] = value

    if args.dry_run:
        chosen = "без обложки" if keep is None else f"[{keep.index}] {keep.type_name}, {keep.size} Б"
        print(f"{args.file}: будет оставлена обложка {chosen}; файл не изменён")
        return 0

    try:
        after = clean_file(
            args.file,
            keep=keep,
            metadata=metadata,
            target_id3=args.id3,
            backup=not args.no_backup,
        )
    except (FileNotFoundError, UnsupportedFormat) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ошибка записи: {exc}", file=sys.stderr)
        return 1

    print(f"готово: {after.path}")
    print(f"  теги    : {', '.join(after.tag_versions) or 'нет'}")
    print(f"  обложек : {len(after.pictures)}")
    for picture in after.pictures:
        print(f"    [{picture.index}] {picture.type_name}, {picture.resolution}, {picture.size} Б")
    if not args.no_backup:
        print(f"  бэкап   : {after.path.name}.bak")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "inspect":
        return _cmd_inspect(args)
    if args.command == "clean":
        return _cmd_clean(args)
    parser.print_help()
    return 1
