const ROW_HEIGHT = 64;

const state = {
  tracks: [],
  total: 0,
  sort: "artist",
  query: "",
  view: "library",
  currentId: null,
  queue: [],
  queueIndex: -1,
  shuffle: false,
  repeat: "off",
  folders: [],
  scanTimer: null,
  editing: null,
  lyrics: null,
  lyricLines: [],
  lyricsFollow: true,
  loading: true,
};

const el = {
  view: document.getElementById("view"),
  crumbs: document.getElementById("crumbs"),
  search: document.getElementById("search"),
  sort: document.getElementById("sort"),
  nav: document.getElementById("nav"),
  audio: document.getElementById("audio"),
  play: document.getElementById("play"),
  prev: document.getElementById("prev"),
  next: document.getElementById("next"),
  shuffle: document.getElementById("shuffle"),
  repeat: document.getElementById("repeat"),
  seek: document.getElementById("seek"),
  elapsed: document.getElementById("elapsed"),
  duration: document.getElementById("duration"),
  volume: document.getElementById("volume"),
  mute: document.getElementById("mute"),
  nowCover: document.getElementById("now-cover"),
  nowTitle: document.getElementById("now-title"),
  nowArtist: document.getElementById("now-artist"),
  now: document.getElementById("now"),
  nowplaying: document.getElementById("nowplaying"),
  npBackdrop: document.getElementById("np-backdrop"),
  npCover: document.getElementById("np-cover"),
  npTitle: document.getElementById("np-title"),
  npArtist: document.getElementById("np-artist"),
  npAlbum: document.getElementById("np-album"),
  npClose: document.getElementById("np-close"),
  npPlay: document.getElementById("np-play"),
  npPrev: document.getElementById("np-prev"),
  npNext: document.getElementById("np-next"),
  npShuffle: document.getElementById("np-shuffle"),
  npRepeat: document.getElementById("np-repeat"),
  npSeek: document.getElementById("np-seek"),
  npElapsed: document.getElementById("np-elapsed"),
  npDuration: document.getElementById("np-duration"),
  npMute: document.getElementById("np-mute"),
  npVolume: document.getElementById("np-volume"),
  npEdit: document.getElementById("np-edit"),
  npLyrics: document.getElementById("np-lyrics"),
  npBody: document.getElementById("np-body"),
  npLyricsEdit: document.getElementById("np-lyrics-edit"),
  lyricsModal: document.getElementById("lyrics-modal"),
  lyricsForm: document.getElementById("lyrics-form"),
  lyricsText: document.getElementById("lyrics-text"),
  lyricsFile: document.getElementById("lyrics-file"),
  lyricsClose: document.getElementById("lyrics-close"),
  lyricsCancel: document.getElementById("lyrics-cancel"),
  lyricsClear: document.getElementById("lyrics-clear"),
  lyricsFollow: document.getElementById("lyrics-follow"),
  editCurrent: document.getElementById("edit-current"),
  editModal: document.getElementById("edit-modal"),
  editForm: document.getElementById("edit-form"),
  editFields: document.getElementById("edit-fields"),
  editFile: document.getElementById("edit-file"),
  editClose: document.getElementById("edit-close"),
  editCancel: document.getElementById("edit-cancel"),
  editSave: document.getElementById("edit-save"),
  spectrum: document.getElementById("spectrum"),
  toast: document.getElementById("toast"),
  addFolder: document.getElementById("add-folder"),
  scanHint: document.getElementById("scan-hint"),
};

let toastTimer = null;
let audioContext = null;
let analyser = null;
let spectrumFrame = null;
let listBody = null;
let rowsEl = null;

const ICONS = {
  play: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M7 5h4v14H7zm6 0h4v14h-4z"/></svg>',
  prev: '<svg viewBox="0 0 24 24"><path d="M6 5h2v14H6zm2 7 12-7v14z"/></svg>',
  next: '<svg viewBox="0 0 24 24"><path d="M16 5h2v14h-2zM4 5l12 7-12 7z"/></svg>',
  shuffle: '<svg viewBox="0 0 24 24"><path d="M17 3l4 4-4 4V8h-2.2c-1 0-1.6.4-2.3 1.4l-1.1 1.6-1.3-1.8C9.3 8.1 8.4 7.5 7.2 7.5H3v2h4.2c.5 0 .9.2 1.4.8l1.6 2.2-1.7 2.4c-.4.6-.8.8-1.3.8H3v2h4.2c1.2 0 2.1-.6 2.9-1.7l1.3-1.8 1.1 1.6c.7 1 1.3 1.4 2.3 1.4H17v3l4-4-4-4v3h-1.9c-.5 0-.9-.2-1.4-.9l-1.5-2.1 1.6-2.3c.4-.6.8-.8 1.3-.8H17z"/></svg>',
  repeat: '<svg viewBox="0 0 24 24"><path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z"/></svg>',
  "repeat-one": '<svg viewBox="0 0 24 24"><path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z"/><path d="M11 15h1.6v-4H11l-.9.9v.9h.9z"/></svg>',
  volume: '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4zm12.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4z"/></svg>',
  mute: '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4zm12.6 3 2.4 2.4-1.4 1.4L15.2 13l-2.4 2.4-1.4-1.4L13.8 12l-2.4-2.4 1.4-1.4L15.2 11l2.4-2.4 1.4 1.4z"/></svg>',
  lyrics: '<svg viewBox="0 0 24 24"><path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h10v2H4z"/></svg>',
};

function setIcon(button, name) {
  if (button) button.innerHTML = ICONS[name] || "";
}

for (const [id, name] of Object.entries({
  shuffle: "shuffle", prev: "prev", play: "play", next: "next", repeat: "repeat",
  mute: "volume", "np-shuffle": "shuffle", "np-prev": "prev", "np-play": "play",
  "np-next": "next", "np-repeat": "repeat", "np-mute": "volume", "np-lyrics-edit": "lyrics",
})) {
  setIcon(document.getElementById(id), name);
}

/* ------------------------------------------------------------------ utils */
function formatTime(seconds) {
  if (!seconds || Number.isNaN(seconds)) return "0:00";
  const total = Math.max(0, Math.round(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function coverMarkup(track, size = 64) {
  if (track.cover_hash) {
    return `<img loading="lazy" src="${API.thumb(track.cover_hash, size)}" alt="">`;
  }
  return `<span class="vinyl"></span>`;
}

function toast(message) {
  el.toast.textContent = message;
  el.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.toast.hidden = true; }, 2600);
}

/* ------------------------------------------------------------------- list */
function rowMarkup(track) {
  const playing = track.id === state.currentId ? " playing" : "";
  return `
    <div class="row${playing}" data-id="${track.id}">
      <div class="row-cover">${coverMarkup(track)}</div>
      <div class="row-main">
        <div class="row-title">${escapeHtml(track.title || "Без названия")}</div>
        <div class="row-artist">${escapeHtml(track.artist || "Неизвестный")}</div>
      </div>
      <div class="row-album">${escapeHtml(track.album || "")}</div>
      <div class="row-time">
        <button class="row-edit" data-edit="${track.id}" title="Изменить метаданные">✎</button>
        <span>${formatTime(track.duration)}</span>
      </div>
    </div>`;
}

function renderRows() {
  if (!listBody || !rowsEl) return;
  const scrollTop = listBody.scrollTop;
  const height = listBody.clientHeight || 600;
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 6);
  const end = Math.min(state.tracks.length, Math.ceil((scrollTop + height) / ROW_HEIGHT) + 6);
  rowsEl.style.transform = `translateY(${start * ROW_HEIGHT}px)`;
  rowsEl.innerHTML = state.tracks.slice(start, end).map(rowMarkup).join("");
}

function renderLibrary() {
  if (state.loading) {
    el.view.innerHTML = `
      <div class="empty">
        <div>
          <h2>Загружаю библиотеку…</h2>
          <p>Читаю индекс папок и обложки.</p>
        </div>
      </div>`;
    listBody = rowsEl = null;
    return;
  }
  if (!state.tracks.length) {
    el.view.innerHTML = `
      <div class="empty">
        <div>
          <h2>Библиотека пуста</h2>
          <p>Добавьте папку с музыкой — χορεία просканирует её и покажет треки.</p>
        </div>
      </div>`;
    listBody = rowsEl = null;
    return;
  }
  el.view.innerHTML = `
    <div class="list">
      <div class="list-head">
        <span></span><span>Название</span><span>Альбом</span><span>Время</span>
      </div>
      <div class="list-body" id="list-body">
        <div class="list-body-height" id="list-height"></div>
        <div class="rows" id="rows"></div>
      </div>
    </div>`;
  listBody = document.getElementById("list-body");
  rowsEl = document.getElementById("rows");
  document.getElementById("list-height").style.height = `${state.tracks.length * ROW_HEIGHT}px`;
  rowsEl.style.position = "absolute";
  rowsEl.style.left = "0";
  rowsEl.style.right = "0";
  rowsEl.style.top = "0";
  listBody.addEventListener("scroll", renderRows, { passive: true });
  renderRows();
}

/* ------------------------------------------------------------------ data */
async function loadTracks() {
  try {
    const payload = await API.get("tracks", {
      sort: state.sort, q: state.query, limit: 1000, offset: 0,
    });
    state.tracks = payload.tracks;
    state.total = payload.total;
    state.loading = false;
    if (state.view === "library") renderLibrary();
    updatePlayingMark();
  } catch (error) {
    state.loading = false;
    toast(`Не удалось загрузить треки: ${error.message}`);
  }
}

function updatePlayingMark() {
  if (!rowsEl) return;
  rowsEl.querySelectorAll(".row").forEach((row) => {
    row.classList.toggle("playing", Number(row.dataset.id) === state.currentId);
  });
}

/* ----------------------------------------------------------------- player */
function trackById(id) {
  return state.tracks.find((track) => track.id === id) || null;
}

function setQueueFromList() {
  state.queue = state.tracks.map((track) => track.id);
  state.queueIndex = state.queue.indexOf(state.currentId);
}

function playTrack(id) {
  const track = trackById(id);
  if (!track) return;
  if (!state.queue.length || !state.queue.includes(id)) setQueueFromList();
  state.queueIndex = state.queue.indexOf(id);
  state.currentId = id;
  el.audio.src = API.media(id);
  el.audio.play().catch(() => {});
  updateNow(track);
  loadLyrics(id);
  updatePlayingMark();
  if (window.pywebview?.api?.played) window.pywebview.api.played(id).catch(() => {});
}

function updateNow(track) {
  el.nowTitle.textContent = track.title || "Без названия";
  el.nowArtist.textContent = track.artist || "";
  el.npTitle.textContent = track.title || "";
  el.npArtist.textContent = track.artist || "";
  el.npAlbum.textContent = track.album || "";
  setCover(el.nowCover, track, 320);
  setCover(el.npCover, track, 640);
  if (track.cover_hash) {
    el.npBackdrop.style.backgroundImage = `url("${API.thumb(track.cover_hash, 320)}")`;
    requestAnimationFrame(() => el.npBackdrop.classList.add("ready"));
  } else {
    el.npBackdrop.style.backgroundImage = "";
    el.npBackdrop.classList.remove("ready");
  }
  document.title = `${track.title || "χορεία"} — χορεία`;
  syncTransport();
  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: track.title || "",
      artist: track.artist || "",
      album: track.album || "",
      artwork: track.cover_hash ? [{ src: API.thumb(track.cover_hash, 640), sizes: "640x640", type: "image/jpeg" }] : [],
    });
  }
}

function setCover(container, track, size) {
  container.innerHTML = coverMarkup(track, size);
  const image = container.querySelector("img");
  if (!image) return;
  image.classList.add("cover-fade");
  const show = () => image.classList.add("cover-in");
  if (image.complete && image.naturalWidth) show();
  else image.addEventListener("load", show, { once: true });
}

function nextTrack(step = 1) {
  if (!state.queue.length) return;
  if (state.repeat === "one" && step === 1) {
    el.audio.currentTime = 0;
    el.audio.play().catch(() => {});
    return;
  }
  let index;
  if (state.shuffle) {
    index = Math.floor(Math.random() * state.queue.length);
    if (state.queue.length > 1 && state.queue[index] === state.currentId) {
      index = (index + 1) % state.queue.length;
    }
  } else {
    index = state.queueIndex + step;
    if (index >= state.queue.length) {
      if (state.repeat === "all") index = 0;
      else { el.audio.pause(); return; }
    }
    if (index < 0) {
      if (state.repeat === "all") index = state.queue.length - 1;
      else index = 0;
    }
  }
  playTrack(state.queue[index]);
}

function togglePlay() {
  if (!state.currentId) {
    if (state.tracks.length) playTrack(state.tracks[0].id);
    return;
  }
  if (el.audio.paused) el.audio.play().catch(() => {});
  else el.audio.pause();
}

function syncPlayIcon() {
  syncTransport();
}

function syncTransport() {
  const playing = !el.audio.paused && Boolean(state.currentId);
  setIcon(el.play, playing ? "pause" : "play");
  setIcon(el.npPlay, playing ? "pause" : "play");

  for (const button of [el.shuffle, el.npShuffle]) button.classList.toggle("on", state.shuffle);
  for (const button of [el.repeat, el.npRepeat]) {
    button.classList.toggle("on", state.repeat !== "off");
    setIcon(button, state.repeat === "one" ? "repeat-one" : "repeat");
  }

  const duration = el.audio.duration || 0;
  const ratio = duration ? el.audio.currentTime / duration : 0;
  const pairs = [
    [el.seek, el.elapsed, el.duration],
    [el.npSeek, el.npElapsed, el.npDuration],
  ];
  for (const [seek, elapsed, total] of pairs) {
    seek.value = String(Math.round(ratio * 1000));
    seek.style.background = `linear-gradient(90deg, var(--accent) ${ratio * 100}%, var(--surface-3) 0)`;
    elapsed.textContent = formatTime(el.audio.currentTime);
    total.textContent = formatTime(duration);
  }

  el.npVolume.value = String(Math.round(el.audio.volume * 100));
  const muted = el.audio.muted;
  setIcon(el.mute, muted ? "mute" : "volume");
  setIcon(el.npMute, muted ? "mute" : "volume");
  syncLyric();
}

/* ------------------------------------------------------------- now playing */
function openNowPlaying() {
  if (!state.currentId) return;
  el.nowplaying.hidden = false;
  document.body.classList.add("np-open");
  startSpectrum();
  requestAnimationFrame(() => {
    if (state.lyricsFollow) scrollToActive();
  });
}

function closeNowPlaying() {
  el.nowplaying.hidden = true;
  document.body.classList.remove("np-open");
  stopSpectrum();
}

function ensureAudioGraph() {
  if (audioContext) return;
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaElementSource(el.audio);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 128;
    source.connect(analyser);
    analyser.connect(audioContext.destination);
  } catch (error) {
    audioContext = null;
  }
}

function startSpectrum() {
  ensureAudioGraph();
  if (!analyser) return;
  if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
  const canvas = el.spectrum;
  const ctx = canvas.getContext("2d");
  const data = new Uint8Array(analyser.frequencyBinCount);
  const draw = () => {
    analyser.getByteFrequencyData(data);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bars = 48;
    const width = canvas.width / bars;
    for (let i = 0; i < bars; i += 1) {
      const value = data[Math.floor((i / bars) * data.length)] / 255;
      const height = Math.max(2, value * canvas.height);
      ctx.fillStyle = `rgba(34, 197, 94, ${0.25 + value * 0.75})`;
      ctx.fillRect(i * width + 1, canvas.height - height, width - 2, height);
    }
    spectrumFrame = requestAnimationFrame(draw);
  };
  stopSpectrum();
  draw();
}

function stopSpectrum() {
  if (spectrumFrame) cancelAnimationFrame(spectrumFrame);
  spectrumFrame = null;
}

/* ------------------------------------------------------------------ views */
async function renderFolders() {
  try {
    const payload = await API.get("folders");
    state.folders = payload.folders;
  } catch (error) {
    state.folders = [];
  }
  if (!state.folders.length) {
    el.view.innerHTML = `
      <div class="empty"><div>
        <h2>Папок пока нет</h2>
        <p>Нажмите «Добавить папку» слева. χορεία обходит вложенные папки исполнителей и альбомов.</p>
      </div></div>`;
    return;
  }
  el.view.innerHTML = `<div class="scroll">${state.folders.map((folder) => `
    <div class="row" data-folder="${escapeHtml(folder.path)}">
      <div class="row-cover">▤</div>
      <div class="row-main">
        <div class="row-title">${escapeHtml(folder.path.split(/[\\/]/).pop())}</div>
        <div class="row-artist">${escapeHtml(folder.path)}</div>
      </div>
      <div class="row-album"></div>
      <div class="row-time">
        <button class="row-remove" data-remove="${folder.id}" title="Убрать папку из библиотеки">✕</button>
        <span>⟳</span>
      </div>
    </div>`).join("")}</div>`;
}

async function removeFolder(folderId) {
  if (!window.confirm("Убрать папку из библиотеки? Файлы на диске останутся.")) return;
  try {
    await API.del(`folders/${folderId}`);
    toast("Папка убрана из библиотеки");
    await loadTracks();
    renderFolders();
  } catch (error) {
    toast(`Не удалось убрать папку: ${error.message}`);
  }
}

function renderPlaceholder(title, text) {
  el.view.innerHTML = `<div class="empty"><div><h2>${title}</h2><p>${text}</p></div></div>`;
}

function switchView(view) {
  state.view = view;
  el.nav.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === view);
  });
  const titles = { library: "Библиотека", folders: "Папки", playlists: "Плейлисты", online: "Интернет" };
  el.crumbs.textContent = titles[view] || "";
  if (view === "library") renderLibrary();
  if (view === "folders") renderFolders();
  if (view === "playlists") renderPlaceholder("Плейлисты", "Появятся на следующем этапе: создание, порядок треков, перетаскивание.");
  if (view === "online") renderPlaceholder("Интернет", "Поиск и скачивание с hitmos.fm появятся на этапе 5.");
}

/* ------------------------------------------------------------------- scan */
async function addFolder() {
  let folder = null;
  if (window.pywebview?.api?.pick_folder) {
    folder = await window.pywebview.api.pick_folder();
  } else {
    folder = window.prompt("Путь к папке с музыкой", "C:\\\\Music");
  }
  if (!folder) return;
  if (Array.isArray(folder)) folder = folder[0];
  try {
    await API.post("folders", { path: folder });
    const result = await API.post("scan", { path: folder });
    if (!result.started) toast("Сканирование уже идёт");
    pollScan();
  } catch (error) {
    toast(`Не удалось добавить папку: ${error.message}`);
  }
}

function pollScan() {
  clearInterval(state.scanTimer);
  state.scanTimer = setInterval(async () => {
    try {
      const status = await API.get("scan/status");
      if (status.running) {
        el.scanHint.textContent = `Сканирование ${status.done}/${status.total}`;
        return;
      }
      clearInterval(state.scanTimer);
      el.scanHint.textContent = "";
      if (status.error) toast(`Сканирование: ${status.error}`);
      else if (status.result) {
        const { added, updated, removed } = status.result;
        toast(`Добавлено ${added}, обновлено ${updated}, удалено ${removed}`);
      }
      await loadTracks();
      if (state.view === "folders") renderFolders();
    } catch (error) {
      clearInterval(state.scanTimer);
      el.scanHint.textContent = "";
    }
  }, 700);
}

/* ---------------------------------------------------------------- editor */
const EDIT_FIELDS = [
  ["title", "Название"],
  ["artist", "Исполнитель"],
  ["album", "Альбом"],
  ["album_artist", "Исполнитель альбома"],
  ["track", "Трек"],
  ["disc", "Диск"],
  ["year", "Год"],
  ["genre", "Жанр"],
];

function fieldValue(track, key) {
  if (key === "track") return track.track_no ?? "";
  if (key === "disc") return track.disc_no ?? "";
  return track[key] ?? "";
}

function openEditor(trackId) {
  const track = trackById(Number(trackId));
  if (!track) {
    toast("Сначала выберите трек");
    return;
  }
  state.editing = track;
  el.editFile.textContent = track.path;
  el.editFields.innerHTML = EDIT_FIELDS.map(([key, label]) => `
    <div class="field">
      <label for="edit-${key}">${label}</label>
      <input id="edit-${key}" data-key="${key}" value="${escapeHtml(fieldValue(track, key))}">
    </div>`).join("");
  el.editModal.hidden = false;
  requestAnimationFrame(() => el.editFields.querySelector("input")?.focus());
}

function closeEditor() {
  el.editModal.hidden = true;
  state.editing = null;
}

async function saveEditor(event) {
  event.preventDefault();
  if (!state.editing) return;
  const payload = {};
  el.editFields.querySelectorAll("input").forEach((input) => {
    payload[input.dataset.key] = input.value;
  });
  el.editSave.disabled = true;
  el.editSave.textContent = "Сохраняю…";
  try {
    const response = await API.post(`tracks/${state.editing.id}`, payload);
    const updated = response.track;
    const index = state.tracks.findIndex((item) => item.id === updated.id);
    if (index >= 0) state.tracks[index] = updated;
    if (state.currentId === updated.id) updateNow(updated);
    closeEditor();
    renderLibrary();
    syncTransport();
    toast("Метаданные записаны, файл сохранён");
  } catch (error) {
    toast(`Не удалось сохранить: ${error.message}`);
  } finally {
    el.editSave.disabled = false;
    el.editSave.textContent = "Сохранить";
  }
}

/* ---------------------------------------------------------------- lyrics */
async function loadLyrics(trackId) {
  state.lyrics = null;
  state.lyricLines = [];
  state.lyricsFollow = true;
  el.lyricsFollow.hidden = true;
  try {
    const data = await API.get(`lyrics/${trackId}`);
    state.lyrics = data.lyrics;
  } catch (error) {
    state.lyrics = null;
  }
  renderLyrics();
}

function renderLyrics() {
  const box = el.npLyrics;
  const hasText = Boolean(
    state.lyrics && ((state.lyrics.synced || "").trim() || (state.lyrics.plain || "").trim())
  );
  el.npBody.classList.toggle("with-lyrics", hasText);
  if (!hasText) {
    el.lyricsFollow.hidden = true;
  }
  if (!state.lyrics) {
    box.innerHTML = '<div class="lyrics-empty">Текста нет — нажмите кнопку текста внизу.</div>';
    return;
  }
  const synced = state.lyrics.synced;
  if (synced) {
    const lines = [];
    for (const raw of synced.split("\n")) {
      const match = raw.match(/^\[(\d{1,3}):(\d{1,2}(?:[.,]\d{1,3})?)\]\s*(.*)$/);
      if (match) {
        lines.push({
          time: Number(match[1]) * 60 + Number(match[2].replace(",", ".")),
          text: match[3].trim(),
        });
      }
    }
    state.lyricLines = lines;
    box.innerHTML = lines
      .map((line) => `<div class="lyric-line" data-time="${line.time}">${escapeHtml(line.text || "♪")}</div>`)
      .join("");
    syncLyric();
    if (state.lyricsFollow) requestAnimationFrame(scrollToActive);
  } else {
    box.innerHTML = `<div class="lyrics-plain">${escapeHtml(state.lyrics.plain || "")}</div>`;
  }
}

function scrollToActive() {
  const active = el.npLyrics.querySelector(".lyric-line.active");
  if (active) active.scrollIntoView({ block: "center", behavior: "smooth" });
}

function setFollow(value) {
  state.lyricsFollow = value;
  el.lyricsFollow.hidden = value;
  if (value) scrollToActive();
}

function syncLyric() {
  if (!state.lyricLines.length) return;
  const current = el.audio.currentTime;
  let index = 0;
  for (let i = 0; i < state.lyricLines.length; i += 1) {
    if (state.lyricLines[i].time <= current) index = i;
    else break;
  }
  const nodes = el.npLyrics.querySelectorAll(".lyric-line");
  nodes.forEach((node, i) => node.classList.toggle("active", i === index));
  if (nodes[index] && !el.nowplaying.hidden && state.lyricsFollow) {
    nodes[index].scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

function openLyricsEditor() {
  const track = trackById(state.currentId);
  if (!track) {
    toast("Сначала включите трек");
    return;
  }
  el.lyricsFile.textContent = `${track.artist || ""} — ${track.title || ""}`;
  el.lyricsText.value = state.lyrics ? state.lyrics.synced || state.lyrics.plain || "" : "";
  el.lyricsModal.hidden = false;
  requestAnimationFrame(() => el.lyricsText.focus());
}

function closeLyricsEditor() {
  el.lyricsModal.hidden = true;
}

async function saveLyrics(event) {
  event.preventDefault();
  if (!state.currentId) return;
  try {
    await API.post(`lyrics/${state.currentId}`, { text: el.lyricsText.value });
    closeLyricsEditor();
    await loadLyrics(state.currentId);
    toast("Текст сохранён");
  } catch (error) {
    toast(`Не удалось сохранить текст: ${error.message}`);
  }
}

async function clearLyrics() {
  if (!state.currentId) return;
  if (!window.confirm("Удалить текст у этого трека?")) return;
  try {
    await API.del(`lyrics/${state.currentId}`);
    closeLyricsEditor();
    await loadLyrics(state.currentId);
    toast("Текст удалён");
  } catch (error) {
    toast(`Не удалось удалить текст: ${error.message}`);
  }
}

/* ---------------------------------------------------------------- wiring */
el.view.addEventListener("click", (event) => {
  const remove = event.target.closest(".row-remove");
  if (remove) {
    event.stopPropagation();
    removeFolder(Number(remove.dataset.remove));
    return;
  }
  const edit = event.target.closest(".row-edit");
  if (edit) {
    event.stopPropagation();
    openEditor(Number(edit.dataset.edit));
    return;
  }
  const row = event.target.closest(".row");
  if (!row) return;
  if (row.dataset.folder) {
    API.post("scan", { path: row.dataset.folder }).then(pollScan).catch(() => {});
    return;
  }
  if (row.dataset.id) playTrack(Number(row.dataset.id));
});

el.nav.addEventListener("click", (event) => {
  const item = event.target.closest(".nav-item");
  if (item) switchView(item.dataset.view);
});

let searchTimer = null;
el.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.query = el.search.value.trim();
    loadTracks();
  }, 220);
});

el.sort.addEventListener("change", () => {
  state.sort = el.sort.value;
  loadTracks();
});

el.play.addEventListener("click", togglePlay);
el.prev.addEventListener("click", () => nextTrack(-1));
el.next.addEventListener("click", () => nextTrack(1));

el.shuffle.addEventListener("click", () => {
  state.shuffle = !state.shuffle;
  el.shuffle.classList.toggle("on", state.shuffle);
  toast(state.shuffle ? "Случайный порядок" : "Обычный порядок");
});

el.repeat.addEventListener("click", () => {
  state.repeat = state.repeat === "off" ? "all" : state.repeat === "all" ? "one" : "off";
  el.repeat.classList.toggle("on", state.repeat !== "off");
  el.repeat.textContent = state.repeat === "one" ? "↻¹" : "↻";
  toast(state.repeat === "off" ? "Повтор выключен" : state.repeat === "all" ? "Повтор списка" : "Повтор трека");
});

el.audio.addEventListener("play", syncPlayIcon);
el.audio.addEventListener("pause", syncPlayIcon);
el.audio.addEventListener("loadedmetadata", syncTransport);
el.audio.addEventListener("durationchange", syncTransport);
el.audio.addEventListener("timeupdate", syncTransport);
el.audio.addEventListener("ended", () => nextTrack(1));
el.audio.addEventListener("error", () => toast("Не удалось воспроизвести файл"));

el.seek.addEventListener("input", () => {
  const duration = el.audio.duration || 0;
  if (duration) el.audio.currentTime = (Number(el.seek.value) / 1000) * duration;
});

el.volume.addEventListener("input", () => {
  el.audio.volume = Number(el.volume.value) / 100;
  el.mute.textContent = el.audio.volume === 0 ? "▯" : "▮";
});

el.mute.addEventListener("click", () => {
  el.audio.muted = !el.audio.muted;
  el.mute.textContent = el.audio.muted ? "▯" : "▮";
});

el.now.addEventListener("click", openNowPlaying);
el.npClose?.addEventListener("click", closeNowPlaying);
el.nowplaying.addEventListener("click", (event) => {
  if (event.target === el.nowplaying || event.target === el.npBackdrop) closeNowPlaying();
});

el.npPlay.addEventListener("click", togglePlay);
el.npPrev.addEventListener("click", () => nextTrack(-1));
el.npNext.addEventListener("click", () => nextTrack(1));
el.npShuffle.addEventListener("click", () => el.shuffle.click());
el.npRepeat.addEventListener("click", () => el.repeat.click());
el.npSeek.addEventListener("input", () => {
  const duration = el.audio.duration || 0;
  if (duration) el.audio.currentTime = (Number(el.npSeek.value) / 1000) * duration;
});
el.npVolume.addEventListener("input", () => {
  el.audio.volume = Number(el.npVolume.value) / 100;
  el.volume.value = el.npVolume.value;
});
el.npMute.addEventListener("click", () => {
  el.audio.muted = !el.audio.muted;
  syncTransport();
});

el.editCurrent.addEventListener("click", () => openEditor(state.currentId));
el.npEdit.addEventListener("click", () => openEditor(state.currentId));
el.editForm.addEventListener("submit", saveEditor);
el.editClose.addEventListener("click", closeEditor);
el.editCancel.addEventListener("click", closeEditor);
el.editModal.addEventListener("click", (event) => {
  if (event.target === el.editModal) closeEditor();
});

el.npLyricsEdit.addEventListener("click", openLyricsEditor);
el.lyricsForm.addEventListener("submit", saveLyrics);
el.lyricsClose.addEventListener("click", closeLyricsEditor);
el.lyricsCancel.addEventListener("click", closeLyricsEditor);
el.lyricsClear.addEventListener("click", clearLyrics);
el.lyricsModal.addEventListener("click", (event) => {
  if (event.target === el.lyricsModal) closeLyricsEditor();
});

el.lyricsFollow.addEventListener("click", () => setFollow(true));
el.npLyrics.addEventListener("wheel", () => setFollow(false), { passive: true });
el.npLyrics.addEventListener("touchmove", () => setFollow(false), { passive: true });
el.npLyrics.addEventListener("click", (event) => {
  const line = event.target.closest(".lyric-line");
  if (!line || line.dataset.time === undefined) return;
  el.audio.currentTime = Number(line.dataset.time);
  syncLyric();
});

document.addEventListener("keydown", (event) => {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return;
  if (event.code === "Space") { event.preventDefault(); togglePlay(); }
  if (event.code === "ArrowRight") { event.preventDefault(); el.audio.currentTime += 5; }
  if (event.code === "ArrowLeft") { event.preventDefault(); el.audio.currentTime -= 5; }
  if (event.code === "KeyN") nextTrack(1);
  if (event.code === "KeyP") nextTrack(-1);
  if (event.code === "KeyM") { el.audio.muted = !el.audio.muted; el.mute.textContent = el.audio.muted ? "▯" : "▮"; }
  if (event.code === "Escape") {
    if (!el.lyricsModal.hidden) closeLyricsEditor();
    else if (!el.editModal.hidden) closeEditor();
    else closeNowPlaying();
  }
  if (event.key === "/") { event.preventDefault(); el.search.focus(); }
});

if ("mediaSession" in navigator) {
  navigator.mediaSession.setActionHandler("play", () => el.audio.play());
  navigator.mediaSession.setActionHandler("pause", () => el.audio.pause());
  navigator.mediaSession.setActionHandler("nexttrack", () => nextTrack(1));
  navigator.mediaSession.setActionHandler("previoustrack", () => nextTrack(-1));
}

el.addFolder.addEventListener("click", addFolder);
el.audio.volume = 0.8;

loadTracks();
