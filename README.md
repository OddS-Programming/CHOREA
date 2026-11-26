# CoverFix

Показывает, что на самом деле лежит в аудиофайле (все версии тегов и все вложенные обложки), и пересобирает файл так, чтобы остались один чистый набор тегов и ровно одна обложка.

## Зачем

mp3tag показывает одну обложку из одного тега. В файле при этом часто есть:

- несколько кадров `APIC` (Front Cover + старая картинка типа Other);
- второй ID3v2-тег в конце файла;
- ID3v1 и APEv2 одновременно;
- обложка во FLAC — в Vorbis-комментарии `metadata_block_picture`;
- несколько картинок в атоме `covr` у m4a.

Плеер или площадка берут не ту, которую вы видите в редакторе. CoverFix показывает всё это списком и удаляет лишнее.

## Запуск

```bash
python -m coverfix inspect "track.mp3"
python -m coverfix inspect --json "track.mp3"
python -m coverfix clean "track.mp3" --keep 2 --title "Название" --artist "Исполнитель"
python -m coverfix clean "track.mp3" --cover cover.jpg --no-backup
python -m coverfix clean "track.mp3" --no-cover
```

Окно: `python -m coverfix.gui` или `CoverFix.exe`.

## Что делает clean

1. Удаляет все версии тегов: ID3v2 (в начале и в конце), ID3v1, APEv2, Vorbis-комментарии, MP4 `ilst`.
2. Удаляет все обложки, включая спрятанные в Vorbis-комментариях.
3. Записывает один набор полей и одну обложку типа Front Cover.
4. Делает `.bak` и пишет через временную копию: при ошибке оригинал не меняется.

## Форматы

mp3, flac, m4a/mp4, ogg, opus. WAV/AIFF и Matroska не поддерживаются, но распознаются: программа скажет, что это за контейнер, вместо молчаливого «обложек нет».

## Разработка

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e . pytest imageio-ffmpeg
.venv/Scripts/python.exe tools/make_assets.py   # один раз, фикстуры уже в репозитории
.venv/Scripts/python.exe -m pytest -q
```

Сборка одного файла:

```bash
.venv/Scripts/python.exe -m pip install pyinstaller
.venv/Scripts/pyinstaller.exe --noconfirm --onefile --windowed --name CoverFix --collect-all tkinterdnd2 tools/run_gui.py
```
