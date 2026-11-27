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
  history: [],
  shuffle: false,
  repeat: "off",
  folders: [],
  scanTimer: null,
  editing: null,
  editCover: { action: "keep", dataUrl: null },
  albumCover: null,
  lyrics: null,
  lyricLines: [],
  lyricIndex: -1,
  followPauseUntil: 0,
  lyricsVisible: true,
  autoLyrics: true,
  accent: "green",
  base: "blue",
  onlineResults: [],
  onlineQuery: "",
  onlineSearched: false,
  onlineJobs: new Map(),
  onlineTimer: null,
  lyricsSkipped: new Set(),
  askResolve: null,
  askMode: "text",
  collection: null,
  folderStack: [],
  selection: new Set(),
  lastSelected: null,
  editTracks: [],
  editBaseline: {},
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
  npBackdropB: document.getElementById("np-backdrop-b"),
  npExit: document.getElementById("np-exit-zone"),
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
  npLyricsToggle: document.getElementById("np-lyrics-toggle"),
  npLeft: document.querySelector(".np-left"),
  npRight: document.querySelector(".np-right"),
  npLyricsEdit: document.getElementById("np-lyrics-edit"),
  lyricsModal: document.getElementById("lyrics-modal"),
  lyricsForm: document.getElementById("lyrics-form"),
  lyricsText: document.getElementById("lyrics-text"),
  lyricsFormat: document.getElementById("lyrics-format"),
  lyricsFile: document.getElementById("lyrics-file"),
  lyricsClose: document.getElementById("lyrics-close"),
  lyricsCancel: document.getElementById("lyrics-cancel"),
  lyricsClear: document.getElementById("lyrics-clear"),
  lyricsFind: document.getElementById("lyrics-find"),
  editCurrent: document.getElementById("edit-current"),
  editModal: document.getElementById("edit-modal"),
  editForm: document.getElementById("edit-form"),
  editFields: document.getElementById("edit-fields"),
  editFile: document.getElementById("edit-file"),
  editClose: document.getElementById("edit-close"),
  editCancel: document.getElementById("edit-cancel"),
  editSave: document.getElementById("edit-save"),
  editCoverPreview: document.getElementById("edit-cover-preview"),
  editCoverPick: document.getElementById("edit-cover-pick"),
  editCoverRemove: document.getElementById("edit-cover-remove"),
  editCoverFile: document.getElementById("edit-cover-file"),
  editCoverHint: document.getElementById("edit-cover-hint"),
  editCoverFind: document.getElementById("edit-cover-find"),
  editCoverResults: document.getElementById("edit-cover-results"),
  coverModal: document.getElementById("cover-modal"),
  coverAlbum: document.getElementById("cover-album"),
  coverPreview: document.getElementById("cover-preview"),
  coverPick: document.getElementById("cover-pick"),
  coverFind: document.getElementById("cover-find"),
  coverRemove: document.getElementById("cover-remove"),
  coverFile: document.getElementById("cover-file"),
  coverHint: document.getElementById("cover-hint"),
  settingsModal: document.getElementById("settings-modal"),
  openSettings: document.getElementById("open-settings"),
  settingsClose: document.getElementById("settings-close"),
  settingAutoLyrics: document.getElementById("setting-autolyrics"),
  settingGenius: document.getElementById("setting-genius"),
  settingGeniusSave: document.getElementById("setting-genius-save"),
  geniusHint: document.getElementById("genius-hint"),
  cacheHint: document.getElementById("cache-hint"),
  settingCacheClear: document.getElementById("setting-cache-clear"),
  lyricsCacheHint: document.getElementById("lyrics-cache-hint"),
  settingLyricsClear: document.getElementById("setting-lyrics-clear"),
  dataHint: document.getElementById("data-hint"),
  settingDataOpen: document.getElementById("setting-data-open"),
  settingVersion: document.getElementById("setting-version"),
  settingsDone: document.getElementById("settings-done"),
  accentChoices: document.getElementById("accent-choices"),
  baseChoices: document.getElementById("base-choices"),
  coverResults: document.getElementById("cover-results"),
  coverSave: document.getElementById("cover-save"),
  coverCancel: document.getElementById("cover-cancel"),
  coverClose: document.getElementById("cover-close"),
  editCoverAlbum: document.getElementById("edit-cover-album"),
  editMultiHint: document.getElementById("edit-multi-hint"),
  askModal: document.getElementById("ask-modal"),
  askTitle: document.getElementById("ask-title"),
  askText: document.getElementById("ask-text"),
  askInput: document.getElementById("ask-input"),
  askOk: document.getElementById("ask-ok"),
  askCancel: document.getElementById("ask-cancel"),
  selectionBar: document.getElementById("selection-bar"),
  selectionCount: document.getElementById("selection-count"),
  selectionEdit: document.getElementById("selection-edit"),
  selectionPlay: document.getElementById("selection-play"),
  selectionClear: document.getElementById("selection-clear"),
  selectionDelete: document.getElementById("selection-delete"),
  uploadFiles: document.getElementById("upload-files"),
  spectrum: document.getElementById("spectrum"),
  toast: document.getElementById("toast"),
  scanHint: document.getElementById("scan-hint"),
};

let toastTimer = null;
let audioContext = null;
let analyser = null;
let spectrumFrame = null;
let listBody = null;
let rowsEl = null;
let backdropLayer = null;

function setBackdrop(track) {
  const next = backdropLayer === el.npBackdrop ? el.npBackdropB : el.npBackdrop;
  if (track.cover_hash) {
    next.classList.remove("plain");
    next.style.backgroundImage = `url("${API.thumb(track.cover_hash, 320)}")`;
  } else {
    next.style.backgroundImage = "";
    next.classList.add("plain");
  }
  next.classList.add("visible");
  if (backdropLayer) backdropLayer.classList.remove("visible");
  backdropLayer = next;
}

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
  eye: '<svg viewBox="0 0 24 24"><path d="M12 5c5 0 9.3 3 11 7-1.7 4-6 7-11 7S2.7 16 1 12c1.7-4 6-7 11-7zm0 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm0-2a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/></svg>',
  "eye-off": '<svg viewBox="0 0 24 24"><path d="M12 5c5 0 9.3 3 11 7a13 13 0 0 1-3.1 4.1l-1.5-1.5A10.9 10.9 0 0 0 20.6 12C19 9.2 15.7 7 12 7c-.7 0-1.4.1-2 .2L8.4 5.6C9.5 5.2 10.7 5 12 5zm0 14c-5 0-9.3-3-11-7a13 13 0 0 1 3.1-4.1l1.5 1.5A10.9 10.9 0 0 0 3.4 12C5 14.8 8.3 17 12 17c.7 0 1.4-.1 2-.2l1.6 1.6c-1.1.4-2.3.6-3.6.6zM3.3 3.3l17.4 17.4-1.4 1.4L1.9 4.7z"/></svg>',
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
function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value <= 0) return "0 Б";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size >= 10 || index === 0 ? Math.round(size) : size.toFixed(1)} ${units[index]}`;
}

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
function rowMarkup(track, selected = false) {
  const playing = track.id === state.currentId ? " playing" : "";
  const chosen = selected ? " selected" : "";
  return `
    <div class="row${playing}${chosen}" data-id="${track.id}">
      <div class="row-cover">${coverMarkup(track)}</div>
      <div class="row-main">
        <div class="row-title">${escapeHtml(track.title || "Без названия")}</div>
        <div class="row-artist">${escapeHtml(track.artist || "Неизвестный")}</div>
      </div>
      <div class="row-album">${escapeHtml(track.album || "")}</div>
      <div class="row-time">
        <button class="row-add" data-add="${track.id}" title="Добавить в плейлист">＋</button>
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
  rowsEl.innerHTML = state.tracks.slice(start, end).map((track) => rowMarkup(track, false)).join("");
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
  return (
    state.tracks.find((track) => track.id === id) ||
    (state.collection ? state.collection.tracks.find((track) => track.id === id) : null) ||
    null
  );
}

function setQueueFromList() {
  state.queue = state.tracks.map((track) => track.id);
  state.queueIndex = state.queue.indexOf(state.currentId);
}

function playTrack(id, record = true) {
  const track = trackById(id);
  if (!track) return;
  if (!state.queue.length || !state.queue.includes(id)) {
    setQueueFromList();
    state.history = [];
  }
  if (record && state.currentId && state.currentId !== id) {
    state.history.push(state.currentId);
    if (state.history.length > 100) state.history.shift();
  }
  state.queueIndex = state.queue.indexOf(id);
  state.currentId = id;
  el.audio.src = API.media(id);
  // Build the WebAudio graph once, before the first sound, so opening the
  // full-screen view later never reroutes the element and never causes a gap.
  ensureAudioGraph();
  if (audioContext?.state === "suspended") audioContext.resume().catch(() => {});
  el.audio.play().catch(() => {});
  updateNow(track);
  loadLyrics(id);
  updatePlayingMark();
  if (window.pywebview?.api?.played) window.pywebview.api.played(id).catch(() => {});
}

function updateNow(track) {
  state.nowSnapshot = [track.title, track.artist, track.album, track.cover_hash].join("\u0000");
  el.nowTitle.textContent = track.title || "Без названия";
  el.nowArtist.textContent = track.artist || "";
  el.npTitle.textContent = track.title || "";
  el.npArtist.textContent = track.artist || "";
  el.npAlbum.textContent = track.album || "";
  setCover(el.nowCover, track, 320);
  setCover(el.npCover, track, 640);
  setBackdrop(track);
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

  if (state.shuffle) {
    if (step < 0) {
      const previous = state.history.pop();
      if (previous !== undefined) {
        playTrack(previous, false);
        return;
      }
    } else {
      const candidates = state.queue.filter(
        (id) => id !== state.currentId && !state.history.slice(-5).includes(id)
      );
      const pool = candidates.length
        ? candidates
        : state.queue.filter((id) => id !== state.currentId);
      const source = pool.length ? pool : state.queue;
      playTrack(source[Math.floor(Math.random() * source.length)]);
      return;
    }
  }

  let index = state.queueIndex + step;
  if (index >= state.queue.length) {
    if (state.repeat === "all") index = 0;
    else { el.audio.pause(); return; }
  }
  if (index < 0) {
    if (state.repeat === "all") index = state.queue.length - 1;
    else index = 0;
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
    if (state.lyricIndex >= 0) scrollToLine(state.lyricIndex, false);
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
  const [accentR, accentG, accentB] = accentRgb();
  const draw = () => {
    analyser.getByteFrequencyData(data);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bars = 48;
    const width = canvas.width / bars;
    for (let i = 0; i < bars; i += 1) {
      const value = data[Math.floor((i / bars) * data.length)] / 255;
      const height = Math.max(2, value * canvas.height);
      ctx.fillStyle = `rgba(${accentR}, ${accentG}, ${accentB}, ${0.25 + value * 0.75})`;
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
  const toolbar = '<div class="playlist-toolbar"><button class="ghost" id="folders-add">＋ Добавить папку</button></div>';
  if (!state.folders.length) {
    el.view.innerHTML = `${toolbar}
      <div class="empty"><div>
        <h2>Папок пока нет</h2>
        <p>Добавьте папку с музыкой или создайте новую.</p>
      </div></div>`;
    return;
  }
  el.view.innerHTML = `${toolbar}<div class="scroll">${state.folders.map((folder) => `
    <div class="row" data-folder="${escapeHtml(folder.path)}">
      <div class="row-cover">▤</div>
      <div class="row-main">
        <div class="row-title">${escapeHtml(folder.path.split(/[\\/]/).pop())}</div>
        <div class="row-artist">${escapeHtml(folder.path)}</div>
      </div>
      <div class="row-album"></div>
      <div class="row-time">
        <button class="row-open" data-open="${escapeHtml(folder.path)}" title="Открыть папку в Проводнике">
          <svg viewBox="0 0 24 24"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
        </button>
        <button class="row-rescan" data-rescan="${escapeHtml(folder.path)}" title="Пересканировать">⟳</button>
        <button class="row-remove" data-remove="${folder.id}" title="Убрать папку из библиотеки">✕</button>
      </div>
    </div>`).join("")}</div>`;
}

async function removeFolder(folderId) {
  const agreed = await askConfirm(
    "Убрать папку из библиотеки?",
    "Файлы на диске останутся, пропадёт только запись в библиотеке."
  );
  if (!agreed) return;
  try {
    const result = await API.del(`folders/${folderId}`);
    toast(
      result.rescanning
        ? "Папка убрана, треки из вложенных папок возвращаются в библиотеку"
        : "Папка убрана из библиотеки"
    );
    await loadTracks();
    await renderFolders();
    if (result.rescanning) pollScan();
  } catch (error) {
    toast(`Не удалось убрать папку: ${error.message}`);
  }
}

/* -------------------------------------------------------------- playlists */
async function renderPlaylists() {
  let playlists = [];
  try {
    playlists = (await API.get("playlists")).playlists;
  } catch (error) {
    toast(`Не удалось загрузить плейлисты: ${error.message}`);
  }
  const toolbar = '<div class="playlist-toolbar"><button class="ghost" id="playlist-new">＋ Новый плейлист</button></div>';
  if (!playlists.length) {
    el.view.innerHTML = `${toolbar}<div class="empty"><div><h2>Плейлистов пока нет</h2>
      <p>Создайте первый и добавляйте треки кнопкой ＋ в списке.</p></div></div>`;
    return;
  }
  el.view.innerHTML = `${toolbar}<div class="scroll">${playlists.map((playlist) => `
    <div class="row" data-playlist="${playlist.id}">
      <div class="row-cover">◈</div>
      <div class="row-main">
        <div class="row-title">${escapeHtml(playlist.name)}</div>
        <div class="row-artist">${playlist.tracks} треков</div>
      </div>
      <div class="row-album"></div>
      <div class="row-time">›</div>
    </div>`).join("")}</div>`;
}

async function createPlaylistPrompt() {
  const name = await askText("Новый плейлист", "", "Название плейлиста");
  if (!name || !name.trim()) return;
  try {
    await API.post("playlists", { name: name.trim() });
    await renderPlaylists();
  } catch (error) {
    toast("Плейлист с таким названием уже есть");
  }
}

async function openPlaylist(id) {
  try {
    const data = await API.get(`playlists/${id}`);
    state.playlist = data;
    state.queue = data.tracks.map((track) => track.id);
    state.queueIndex = -1;
    state.history = [];
    el.crumbs.textContent = data.playlist.name;
    el.view.innerHTML = `
      <div class="playlist-toolbar">
        <button class="ghost" id="playlist-play">▶ Играть</button>
        <span class="hint">${data.tracks.length} треков</span>
        <button class="ghost danger" id="playlist-delete">Удалить</button>
      </div>
      <div class="scroll">${data.tracks.length
        ? data.tracks.map((track) => rowMarkup(track, false)).join("")
        : '<div class="empty"><div><h2>Пусто</h2><p>Добавьте треки кнопкой ＋ в библиотеке.</p></div></div>'}</div>`;
  } catch (error) {
    toast(`Не удалось открыть плейлист: ${error.message}`);
  }
}

function closeMenu() {
  document.querySelectorAll(".menu").forEach((node) => node.remove());
}

function askText(title, value = "", placeholder = "") {
  return new Promise((resolve) => {
    state.askResolve = resolve;
    state.askMode = "text";
    el.askTitle.textContent = title;
    el.askText.hidden = true;
    el.askInput.hidden = false;
    el.askInput.value = value;
    el.askInput.placeholder = placeholder;
    el.askModal.hidden = false;
    requestAnimationFrame(() => {
      el.askInput.focus();
      el.askInput.select();
    });
  });
}

function askConfirm(title, text) {
  return new Promise((resolve) => {
    state.askResolve = resolve;
    state.askMode = "confirm";
    el.askTitle.textContent = title;
    el.askText.textContent = text;
    el.askText.hidden = false;
    el.askInput.hidden = true;
    el.askModal.hidden = false;
  });
}

function closeAsk(result) {
  const resolve = state.askResolve;
  state.askResolve = null;
  el.askModal.hidden = true;
  if (resolve) resolve(result);
}

async function openAddMenu(anchor, trackId) {
  closeMenu();
  let playlists = [];
  try {
    playlists = (await API.get("playlists")).playlists;
  } catch (error) {
    playlists = [];
  }
  const menu = document.createElement("div");
  menu.className = "menu";
  menu.innerHTML =
    playlists.map((item) => `<button data-to="${item.id}">${escapeHtml(item.name)}</button>`).join("") +
    '<button data-new="1">＋ Новый плейлист…</button>';
  const rect = anchor.getBoundingClientRect();
  menu.style.left = `${Math.max(12, Math.min(rect.left - 160, window.innerWidth - 236))}px`;
  menu.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - 280)}px`;
  document.body.appendChild(menu);

  menu.addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    try {
      if (button.dataset.new) {
        const name = await askText("Новый плейлист", "", "Название плейлиста");
        if (!name || !name.trim()) return;
        const created = await API.post("playlists", { name: name.trim() });
        await API.post(`playlists/${created.id}/tracks`, { track_id: trackId });
      } else {
        await API.post(`playlists/${button.dataset.to}/tracks`, { track_id: trackId });
      }
      toast("Добавлено в плейлист");
    } catch (error) {
      toast(`Не удалось добавить: ${error.message}`);
    } finally {
      closeMenu();
    }
  });
}

document.addEventListener("click", (event) => {
  if (!event.target.closest(".menu") && !event.target.closest(".row-add")) closeMenu();
});

/* ------------------------------------------------------- folders/albums */
function folderRow(folder) {
  return `<div class="row" data-subfolder="${escapeHtml(folder.path)}">
    <div class="row-cover">▤</div>
    <div class="row-main">
      <div class="row-title">${escapeHtml(folder.name)}</div>
      <div class="row-artist">${folder.tracks} треков</div>
    </div>
    <div class="row-album"></div>
    <div class="row-time">›</div>
  </div>`;
}

function renderCollection() {
  const collection = state.collection;
  if (!collection) return;
  const counts = [];
  if (collection.kind === "folder") counts.push(`${(collection.folders || []).length} папок`);
  counts.push(`${collection.tracks.length} треков`);
  const parts = [`<div class="playlist-toolbar">
    ${collection.parent ? '<button class="ghost" id="collection-back">← Назад</button>' : ""}
    ${collection.kind === "folder" ? '<button class="ghost" id="folder-new">＋ Новая папка</button><button class="ghost" id="folder-upload">＋ Добавить трек</button>' : ""}
    ${collection.kind === "album" ? '<button class="ghost" id="album-cover">Обложка альбома</button>' : ""}
    <span class="hint">${counts.join(" · ")}</span>
  </div>`, '<div class="scroll">'];
  for (const folder of collection.folders || []) parts.push(folderRow(folder));
  for (const track of collection.tracks) parts.push(rowMarkup(track, state.selection.has(track.id)));
  if (!collection.tracks.length && !(collection.folders || []).length) {
    parts.push('<div class="empty"><div><h2>Пусто</h2><p>Здесь нет проиндексированных треков.</p></div></div>');
  }
  parts.push("</div>");
  el.view.innerHTML = parts.join("");
  updateSelection();
}

async function openFolder(path, push = true) {
  try {
    applyFolderData(await API.get("browse", { path }), push);
  } catch (error) {
    toast(`Не удалось открыть папку: ${error.message}`);
  }
}

function applyFolderData(data, push = true) {
  if (push) state.folderStack.push(data.path);
  state.view = "folder";
  state.collection = {
    kind: "folder",
    path: data.path,
    folders: data.folders,
    tracks: data.tracks,
    signature: data.signature,
    parent: state.folderStack.length > 1,
  };
  state.selection = new Set();
  state.lastSelected = null;
  el.crumbs.textContent = data.path.split(/[\\/]/).filter(Boolean).pop() || data.path;
  renderCollection();
}

async function folderBack() {
  state.folderStack.pop();
  const path = state.folderStack[state.folderStack.length - 1];
  if (path) await openFolder(path, false);
  else switchView("folders");
}

async function renderAlbums() {
  el.crumbs.textContent = "Альбомы";
  let albums = [];
  try {
    albums = (await API.get("albums")).albums;
  } catch (error) {
    toast(`Не удалось загрузить альбомы: ${error.message}`);
  }
  if (!albums.length) {
    el.view.innerHTML = '<div class="empty"><div><h2>Альбомов нет</h2><p>У треков не заполнен тег «Альбом».</p></div></div>';
    return;
  }
  el.view.innerHTML = `<div class="album-grid">${albums.map((album) => `
    <button class="album-card" data-album="${escapeHtml(album.album)}" data-artist="${escapeHtml(album.album_artist || "")}">
      <div class="album-cover">${album.cover_hash
        ? `<img loading="lazy" src="${API.thumb(album.cover_hash, 320)}" alt="">`
        : '<span class="vinyl"></span>'}</div>
      <div class="album-name">${escapeHtml(album.album)}</div>
      <div class="album-artist">${escapeHtml(album.album_artist || "—")} · ${album.tracks}</div>
    </button>`).join("")}</div>`;
}

async function openAlbum(album, artist) {
  try {
    const data = await API.get("albums/tracks", { album, artist });
    state.view = "album";
    state.collection = {
      kind: "album",
      album,
      artist,
      tracks: data.tracks,
      cover_hash: data.cover_hash || "",
      custom_cover: Boolean(data.custom_cover),
      parent: false,
    };
    state.selection = new Set();
    state.lastSelected = null;
    el.crumbs.textContent = album;
    renderCollection();
  } catch (error) {
    toast(`Не удалось открыть альбом: ${error.message}`);
  }
}

/* -------------------------------------------------------------- selection */
function selectTrack(id, event) {
  const ids = (state.collection?.tracks || []).map((track) => track.id);
  if (event.shiftKey && state.lastSelected !== null) {
    const from = ids.indexOf(state.lastSelected);
    const to = ids.indexOf(id);
    if (from >= 0 && to >= 0) {
      const [low, high] = [Math.min(from, to), Math.max(from, to)];
      for (let index = low; index <= high; index += 1) state.selection.add(ids[index]);
    }
  } else if (event.ctrlKey) {
    if (state.selection.has(id)) state.selection.delete(id);
    else state.selection.add(id);
  } else {
    state.selection = new Set([id]);
  }
  state.lastSelected = id;
  updateSelection();
}

function updateSelection() {
  el.selectionBar.hidden = state.selection.size === 0;
  el.selectionCount.textContent = `Выбрано ${state.selection.size}`;
  document.querySelectorAll(".row[data-id]").forEach((row) => {
    row.classList.toggle("selected", state.selection.has(Number(row.dataset.id)));
  });
}

async function createFolder() {
  if (state.view !== "folder" || !state.collection?.path) {
    toast("Сначала откройте папку");
    return;
  }
  const name = await askText("Новая папка", "Новая папка", "Название папки");
  if (!name) return;
  if (/[\\/]/.test(name)) {
    toast("В названии не может быть слэшей");
    return;
  }
  const base = state.collection.path.replace(/[\\/]+$/, "");
  try {
    await API.post("mkdir", { path: `${base}\\${name}` });
    toast(`Папка «${name}» создана`);
    await openFolder(state.collection.path, false);
  } catch (error) {
    toast("Не удалось создать папку: возможно, такое имя уже есть");
  }
}

async function uploadTracks() {
  if (state.view !== "folder" || !state.collection?.path) {
    toast("Сначала откройте папку");
    return;
  }
  el.uploadFiles.click();
}

async function handleUpload(files) {
  if (!files.length || !state.collection?.path) return;
  let added = 0;
  let failed = 0;
  for (const file of files) {
    try {
      const response = await fetch(
        `/api/upload?path=${encodeURIComponent(state.collection.path)}&t=${encodeURIComponent(TOKEN)}`,
        {
          method: "POST",
          headers: {
            "X-Token": TOKEN,
            "X-Filename": encodeURIComponent(file.name),
            "Content-Type": "application/octet-stream",
          },
          body: file,
        }
      );
      if (response.ok) added += 1;
      else failed += 1;
    } catch (error) {
      failed += 1;
    }
  }
  toast(failed ? `Загружено: ${added}, ошибок: ${failed}` : `Загружено треков: ${added}`);
  await openFolder(state.collection.path, false);
  await loadTracks();
}

let refreshing = false;

function sameTrackList(left, right) {
  if (!left || !right || left.length !== right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    const a = left[index];
    const b = right[index];
    if (a.id !== b.id) return false;
    if ((a.title || "") !== (b.title || "")) return false;
    if ((a.artist || "") !== (b.artist || "")) return false;
    if ((a.album || "") !== (b.album || "")) return false;
    if ((a.cover_hash || "") !== (b.cover_hash || "")) return false;
  }
  return true;
}

function freezeViewAnimation() {
  for (const child of el.view.children) child.style.animation = "none";
}

async function refreshCurrentView() {
  if (refreshing) return;
  if (document.hidden) return;
  if (state.selection.size) return;
  if (!el.askModal.hidden || !el.editModal.hidden || !el.lyricsModal.hidden || !el.coverModal.hidden || !el.settingsModal.hidden) return;

  const scroller = () => document.querySelector("#view .scroll, #view .list-body");
  const top = scroller()?.scrollTop || 0;

  refreshing = true;
  try {
    if (state.view === "folder" && state.collection?.path) {
      const data = await API.get("browse", { path: state.collection.path });
      if (data.signature !== state.collection.signature) {
        applyFolderData(data, false);
        freezeViewAnimation();
      }
    } else if (state.view === "library") {
      const payload = await API.get("tracks", {
        sort: state.sort, q: state.query, limit: 1000, offset: 0,
      });
      if (!sameTrackList(payload.tracks, state.tracks) || payload.total !== state.total) {
        state.tracks = payload.tracks;
        state.total = payload.total;
        renderLibrary();
        updatePlayingMark();
        freezeViewAnimation();
      }
    } else if (state.view === "album" && state.collection?.album) {
      const data = await API.get("albums/tracks", {
        album: state.collection.album, artist: state.collection.artist || "",
      });
      if (!sameTrackList(data.tracks, state.collection.tracks)) {
        await openAlbum(state.collection.album, state.collection.artist);
        freezeViewAnimation();
      }
    } else if (state.view === "folders") {
      const payload = await API.get("folders");
      const before = state.folders.map((folder) => folder.path).join("\n");
      const after = payload.folders.map((folder) => folder.path).join("\n");
      if (before !== after) {
        state.folders = payload.folders;
        await renderFolders();
        freezeViewAnimation();
      }
    }
  } catch (error) {
    /* a transient refresh failure must not disturb the current view */
  } finally {
    refreshing = false;
  }

  const again = scroller();
  if (again && top) again.scrollTop = top;
}

function renderPlaceholder(title, text) {
  el.view.innerHTML = `<div class="empty"><div><h2>${title}</h2><p>${text}</p></div></div>`;
}

function switchView(view) {
  state.view = view;
  state.selection = new Set();
  state.lastSelected = null;
  el.selectionBar.hidden = true;
  el.nav.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === view);
  });
  const titles = { library: "Библиотека", albums: "Альбомы", folders: "Папки", playlists: "Плейлисты", online: "Интернет" };
  el.crumbs.textContent = titles[view] || "";
  const onlineMode = view === "online";
  const topSearch = document.getElementById("search");
  const topSort = document.getElementById("sort");
  if (topSearch) topSearch.hidden = onlineMode;
  if (topSort) topSort.hidden = onlineMode;
  if (view === "library") renderLibrary();
  if (view === "albums") renderAlbums();
  if (view === "folders") renderFolders();
  if (view === "playlists") renderPlaylists();
  if (view === "online") openOnline();
}

/* ---------------------------------------------------------------- online */
async function openOnline() {
  try {
    state.folders = (await API.get("folders")).folders;
  } catch (error) {
    /* keep the folders we already know */
  }
  renderOnline();
}

function renderOnline() {
  const folders = state.folders || [];
  const options = folders
    .map((folder) => `<option value="${escapeHtml(folder.path)}">${escapeHtml(folder.path)}</option>`)
    .join("");
  el.view.innerHTML = `
    <div class="playlist-toolbar online-toolbar">
      <input class="search online-search" id="online-query" placeholder="Название или исполнитель"
        value="${escapeHtml(state.onlineQuery)}" autocomplete="off">
      <button class="ghost" id="online-go">Найти</button>
      ${folders.length
        ? `<select class="sort" id="online-folder" title="Куда скачивать">${options}</select>`
        : '<span class="hint">Добавьте папку в библиотеку, чтобы было куда скачивать</span>'}
    </div>
    <div class="scroll" id="online-results"></div>`;
  renderOnlineResults();
  const input = document.getElementById("online-query");
  if (input) {
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        searchOnline();
      }
    });
    if (!state.onlineSearched) input.focus();
  }
}

function onlineRow(item) {
  return `
    <div class="online-row">
      ${item.cover
        ? `<img class="online-cover" src="${escapeHtml(item.cover)}" alt="" loading="lazy">`
        : '<div class="online-cover"></div>'}
      <div class="online-main">
        <div class="online-title">${escapeHtml(item.title || "Без названия")}</div>
        <div class="online-artist">${escapeHtml(item.artist || "Неизвестный исполнитель")}</div>
      </div>
      <div class="online-duration">${escapeHtml(item.duration || "")}</div>
      <button class="ghost online-download" data-download="${escapeHtml(item.id)}">Скачать</button>
    </div>`;
}

function renderOnlineResults() {
  const box = document.getElementById("online-results");
  if (!box) return;
  if (!state.onlineSearched) {
    box.innerHTML = `
      <div class="empty"><div>
        <h2>Поиск музыки</h2>
        <p>Введите название или исполнителя — результаты придут с hitmos.fm.</p>
      </div></div>`;
    return;
  }
  if (!state.onlineResults.length) {
    box.innerHTML = `
      <div class="empty"><div>
        <h2>Ничего не найдено</h2>
        <p>Попробуйте другой запрос.</p>
      </div></div>`;
    return;
  }
  box.innerHTML = state.onlineResults.map(onlineRow).join("");
}

async function searchOnline() {
  const input = document.getElementById("online-query");
  const query = input ? input.value.trim() : "";
  if (!query) return;
  state.onlineQuery = query;
  state.onlineSearched = true;
  const box = document.getElementById("online-results");
  if (box) {
    box.innerHTML = `
      <div class="empty"><div>
        <h2>Ищу…</h2>
        <p>Запрашиваю hitmos.fm.</p>
      </div></div>`;
  }
  try {
    const data = await API.get("online/search", { q: query });
    state.onlineResults = data.results || [];
  } catch (error) {
    state.onlineResults = [];
    toast(`Поиск недоступен: ${error.message}`);
  }
  renderOnlineResults();
}

async function downloadOnline(songId, button) {
  const select = document.getElementById("online-folder");
  const folder = select ? select.value : "";
  if (!folder) {
    toast("Сначала добавьте папку в библиотеку");
    return;
  }
  const song = state.onlineResults.find((item) => item.id === songId);
  button.disabled = true;
  button.textContent = "0%";
  try {
    const data = await API.post("online/download", {
      id: songId,
      folder,
      title: song ? song.title : "",
      artist: song ? song.artist : "",
      cover: song ? song.cover : "",
    });
    state.onlineJobs.set(data.job, { button });
    pollOnline();
  } catch (error) {
    button.disabled = false;
    button.textContent = "Скачать";
    toast(`Не удалось начать загрузку: ${error.message}`);
  }
}

function pollOnline() {
  if (state.onlineTimer) return;
  state.onlineTimer = setInterval(async () => {
    if (!state.onlineJobs.size) {
      clearInterval(state.onlineTimer);
      state.onlineTimer = null;
      return;
    }
    for (const [jobId, entry] of [...state.onlineJobs]) {
      try {
        const data = await API.get("online/progress", { id: jobId });
        const job = data.job;
        if (job.status === "done") {
          state.onlineJobs.delete(jobId);
          entry.button.textContent = "Готово";
          entry.button.disabled = true;
          await loadTracks();
          toast(`Скачано: ${String(job.path).split(/[\\/]/).pop()}`);
        } else if (job.status === "error") {
          state.onlineJobs.delete(jobId);
          entry.button.textContent = "Ошибка";
          entry.button.disabled = false;
          toast(`Не удалось скачать: ${job.error}`);
        } else if (job.total) {
          entry.button.textContent = `${Math.round((job.received / job.total) * 100)}%`;
        } else {
          entry.button.textContent = "…";
        }
      } catch (error) {
        /* a transient status error must not stop polling */
      }
    }
  }, 700);
}

/* ------------------------------------------------------------------- scan */
async function addFolder() {
  const initial = state.collection?.path || state.folders[0]?.path || "";
  let path = null;
  try {
    const picked = await API.post("pick-folder", { initial });
    if (picked.cancelled) return;
    path = picked.path;
  } catch (error) {
    // No native picker (PowerShell missing or blocked): fall back to typing.
    path = await askText(
      "Добавить папку",
      initial || "C:\\",
      "Полный путь к папке с музыкой"
    );
  }
  if (!path) return;
  try {
    await API.post("folders", { path });
    const result = await API.post("scan", { path });
    toast(result.started ? "Папка добавлена, сканирую…" : "Сканирование уже идёт");
    if (state.view === "folders") await renderFolders();
    pollScan();
  } catch (error) {
    toast("Папка не найдена или недоступна");
  }
}

async function addTracksFromPath() {
  const base = state.collection?.path || "C:\\";
  const path = await askText(
    "Добавить треки",
    base.endsWith("\\") ? base : base + "\\",
    "Путь к файлу или папке"
  );
  if (!path) return;
  try {
    const result = await API.post("add-path", { path });
    if (result.kind === "folder") {
      toast(result.started ? "Сканирую папку…" : "Сканирование уже идёт");
      pollScan();
    } else {
      toast(`Добавлено треков: ${result.added}`);
      if (state.view === "folder" && state.collection?.path) {
        await openFolder(state.collection.path, false);
      }
      await loadTracks();
    }
  } catch (error) {
    toast("Путь не найден или это не аудиофайл");
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
      if (state.view === "folders") await renderFolders();
      if (state.view === "folder" && state.collection?.path) {
        await openFolder(state.collection.path, false);
      }
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

function commonValue(tracks, key) {
  const values = new Set(tracks.map((track) => String(fieldValue(track, key))));
  return values.size === 1 ? [...values][0] : null;
}

function openEditor(trackId) {
  openEditorFor([Number(trackId)]);
}

function openEditorFor(ids) {
  const tracks = ids.map((id) => trackById(Number(id))).filter(Boolean);
  if (!tracks.length) {
    toast("Сначала выберите трек");
    return;
  }
  const single = tracks.length === 1;
  state.editTracks = tracks;
  state.editing = tracks[0];
  state.editBaseline = {};
  state.editCover = { action: "keep", dataUrl: null };
  el.editFile.textContent = single ? tracks[0].path : `Выбрано треков: ${tracks.length}`;
  el.editMultiHint.hidden = single;
  el.editCoverFile.value = "";
  el.editCoverAlbum.checked = false;
  el.editCoverAlbum.closest("label").hidden = !single;
  const preview = tracks.find((track) => track.cover_hash);
  setEditCoverPreview(preview ? API.thumb(preview.cover_hash, 320) : "");
  el.editCoverHint.textContent = preview ? "Текущая обложка" : "JPG или PNG, квадрат от 1000×1000";
  el.editCoverResults.hidden = true;
  el.editCoverResults.innerHTML = "";
  el.editFields.innerHTML = EDIT_FIELDS.map(([key, label]) => {
    const value = commonValue(tracks, key);
    state.editBaseline[key] = value;
    return `
      <div class="field">
        <label for="edit-${key}">${label}</label>
        <input id="edit-${key}" data-key="${key}" value="${escapeHtml(value ?? "")}">
      </div>`;
  }).join("");
  el.editModal.hidden = false;
  requestAnimationFrame(() => el.editFields.querySelector("input")?.focus());
}

function setEditCoverPreview(url) {
  el.editCoverPreview.style.backgroundImage = url ? `url("${url}")` : "";
}

async function runCoverSearch({ artist, album, title, results, hint, button }) {
  results.hidden = false;
  results.innerHTML = '<div class="hint">Ищу обложки в интернете…</div>';
  const label = button.textContent;
  button.disabled = true;
  button.textContent = "Ищу…";
  try {
    const data = await API.get("cover-search", { artist, album, title });
    if (!data.results.length) {
      results.innerHTML =
        '<div class="hint">Ничего не нашлось. Заполните исполнителя и альбом и попробуйте снова.</div>';
      return;
    }
    results.innerHTML = data.results
      .map(
        (item) => `
      <button type="button" class="cover-choice" data-key="${item.key}"
        title="${escapeHtml(item.source)}${item.label ? ": " + escapeHtml(item.label) : ""}">
        <img src="${item.thumb}" alt="" loading="lazy">
        <span>${escapeHtml(item.source)}</span>
      </button>`
      )
      .join("");
    results.scrollTop = 0;
    hint.textContent = "Ваша обложка главнее — найденная применится, только если выбрать её.";
  } catch (error) {
    results.innerHTML =
      '<div class="hint">Не удалось получить обложки. Проверьте подключение к интернету.</div>';
  } finally {
    button.disabled = false;
    button.textContent = label || "Найти в интернете";
  }
}

async function findCoverOnline() {
  const track = state.editing;
  if (!track) return;
  const field = (key) => {
    const input = el.editFields.querySelector(`input[data-key="${key}"]`);
    const typed = input ? input.value.trim() : "";
    return typed || String(track[key] || "");
  };
  await runCoverSearch({
    artist: field("artist"),
    album: field("album"),
    title: field("title"),
    results: el.editCoverResults,
    hint: el.editCoverHint,
    button: el.editCoverFind,
  });
}

async function pickOnlineCover(key, button) {
  try {
    const data = await API.get(`cover/${key}`);
    state.editCover = { action: "set", dataUrl: data.cover };
    setEditCoverPreview(data.cover);
    el.editCoverResults
      .querySelectorAll(".cover-choice")
      .forEach((node) => node.classList.toggle("active", node === button));
    el.editCoverHint.textContent = "Выбрана обложка из интернета — применится после «Сохранить».";
  } catch (error) {
    toast("Не удалось загрузить обложку");
  }
}

function closeEditor() {
  el.editModal.hidden = true;
  state.editing = null;
  state.editTracks = [];
  state.editBaseline = {};
  state.editCover = { action: "keep", dataUrl: null };
}

/* --------------------------------------------------------------- settings */
function applyTheme() {
  const root = document.documentElement;
  root.dataset.accent = state.accent;
  root.dataset.base = state.base;
  el.accentChoices.querySelectorAll("[data-accent]").forEach((button) => {
    button.classList.toggle("active", button.dataset.accent === state.accent);
  });
  el.baseChoices.querySelectorAll("[data-base]").forEach((button) => {
    button.classList.toggle("active", button.dataset.base === state.base);
  });
  if (!el.nowplaying.hidden) startSpectrum();
}

function accentRgb() {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue("--accent")
    .trim();
  const match = /^#([0-9a-f]{6})$/i.exec(value);
  if (!match) return [34, 197, 94];
  const number = parseInt(match[1], 16);
  return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
}

async function openSettings() {
  el.settingsModal.hidden = false;
  applyTheme();
  el.settingAutoLyrics.checked = state.autoLyrics;
  el.settingGenius.value = "";
  el.settingVersion.textContent = "";
  el.geniusHint.textContent = "Проверяю…";
  el.cacheHint.textContent = "…";
  el.lyricsCacheHint.textContent = "…";
  try {
    const data = await API.get("diagnostics");
    state.diagnostics = data;
    el.settingVersion.textContent = `χορεία ${data.version}`;
    el.dataHint.textContent = data.data_dir;
    el.lyricsCacheHint.textContent = data.lyrics_cached
      ? `Хранится текстов: ${data.lyrics_cached} · ${formatBytes(data.lyrics_bytes)}`
      : "Сохранённых текстов нет";
    el.cacheHint.textContent = data.cache_bytes
      ? `Занято ${formatBytes(data.cache_bytes)}`
      : "Кэш пуст";
    el.geniusHint.textContent = {
      none: "Не задан — Genius не используется, обложки ищутся в iTunes, Deezer и Cover Art Archive",
      ok: "Токен действителен — Genius участвует в поиске обложек",
      invalid: "Токен не принят Genius (401) — удалите его или вставьте новый",
      error: "Не удалось проверить токен — нет связи с Genius",
    }[data.genius_state] || "Не задан — Genius не используется, обложки ищутся в iTunes, Deezer и Cover Art Archive";
  } catch (error) {
    el.geniusHint.textContent = "Не удалось прочитать настройки";
  }
}

function closeSettings() {
  el.settingsModal.hidden = true;
}

function setAutoLyrics(enabled) {
  state.autoLyrics = enabled;
  savePreference("ui.autoLyrics", enabled ? "1" : "0");
  if (enabled && state.currentId && !lyricsHaveText()) loadLyrics(state.currentId);
}

async function saveGeniusToken() {
  const value = el.settingGenius.value.trim();
  el.settingGeniusSave.disabled = true;
  try {
    await API.post("settings", { key: "genius_token", value });
    el.settingGenius.value = "";
    el.geniusHint.textContent = value
      ? "Токен действителен — Genius участвует в поиске обложек"
      : "Не задан — Genius не используется, обложки ищутся в iTunes, Deezer и Cover Art Archive";
    toast(value ? "Токен Genius сохранён" : "Токен Genius удалён");
  } catch (error) {
    el.geniusHint.textContent = error.message;
    toast("Токен не сохранён");
  } finally {
    el.settingGeniusSave.disabled = false;
  }
}

async function clearLyricsCache() {
  const agreed = await askConfirm(
    "Удалить все тексты?",
    "Сохранённые и найденные тексты будут удалены. При включённом автопоиске они снова найдутся при воспроизведении."
  );
  if (!agreed) return;
  el.settingLyricsClear.disabled = true;
  try {
    const result = await API.del("lyrics");
    state.lyricsSkipped.clear();
    el.lyricsCacheHint.textContent = "Сохранённых текстов нет";
    toast(result.removed ? `Удалено текстов: ${result.removed}` : "Сохранённых текстов не было");
    if (state.currentId) {
      // Do not fetch again right now: the next play will search when enabled.
      state.lyrics = null;
      state.lyricLines = [];
      state.lyricIndex = -1;
      renderLyrics();
    }
  } catch (error) {
    toast("Не удалось очистить тексты");
  } finally {
    el.settingLyricsClear.disabled = false;
  }
}

async function clearThumbCache() {
  el.settingCacheClear.disabled = true;
  try {
    const result = await API.del("cache");
    el.cacheHint.textContent = "Кэш пуст";
    toast(result.removed ? `Освобождено ${formatBytes(result.freed)}` : "Кэш уже пуст");
  } catch (error) {
    toast("Не удалось очистить кэш");
  } finally {
    el.settingCacheClear.disabled = false;
  }
}

async function openDataFolder() {
  const path = state.diagnostics?.data_dir;
  if (!path) return;
  try {
    await API.post("reveal", { path });
  } catch (error) {
    toast("Папка не найдена");
  }
}

/* ------------------------------------------------------------ album cover */
function openAlbumCover() {
  if (state.view !== "album" || !state.collection?.album) {
    toast("Откройте альбом, чтобы сменить его обложку");
    return;
  }
  const tracks = state.collection.tracks || [];
  state.albumCover = {
    album: state.collection.album,
    artist: state.collection.artist || "",
    tracks,
    action: "keep",
    dataUrl: null,
  };
  const subtitle = state.collection.artist ? ` — ${state.collection.artist}` : "";
  el.coverAlbum.textContent = `${state.collection.album}${subtitle} · треков: ${tracks.length}`;
  el.coverFile.value = "";
  el.coverResults.hidden = true;
  el.coverResults.innerHTML = "";
  const preview = state.collection.cover_hash;
  setCoverDialogPreview(preview ? API.thumb(preview, 320) : "");
  el.coverHint.textContent = tracks.length
    ? "Обложка хранится в приложении, файлы и теги не меняются"
    : "В альбоме нет треков";
  el.coverSave.disabled = !tracks.length;
  el.coverModal.hidden = false;
}

function closeAlbumCover() {
  el.coverModal.hidden = true;
  el.coverResults.hidden = true;
  el.coverResults.innerHTML = "";
  state.albumCover = null;
}

function setCoverDialogPreview(url) {
  el.coverPreview.style.backgroundImage = url ? `url("${url}")` : "";
}

async function findAlbumCover() {
  const albumCover = state.albumCover;
  if (!albumCover) return;
  await runCoverSearch({
    artist: albumCover.artist,
    album: albumCover.album,
    title: albumCover.tracks[0]?.title || "",
    results: el.coverResults,
    hint: el.coverHint,
    button: el.coverFind,
  });
}

async function pickAlbumCover(key, button) {
  const albumCover = state.albumCover;
  if (!albumCover) return;
  try {
    const data = await API.get(`cover/${key}`);
    albumCover.action = "set";
    albumCover.dataUrl = data.cover;
    setCoverDialogPreview(data.cover);
    el.coverResults
      .querySelectorAll(".cover-choice")
      .forEach((node) => node.classList.toggle("active", node === button));
    el.coverHint.textContent = "Обложка сохранится в приложении после «Сохранить». Файлы не меняются.";
  } catch (error) {
    toast("Не удалось загрузить обложку");
  }
}

async function saveAlbumCover() {
  const albumCover = state.albumCover;
  if (!albumCover) return;
  if (albumCover.action === "keep") {
    closeAlbumCover();
    return;
  }
  el.coverSave.disabled = true;
  el.coverSave.textContent = "Сохраняю…";
  try {
    const payload = {
      album: albumCover.album,
      album_artist: albumCover.artist,
      action: albumCover.action,
    };
    if (albumCover.action === "set") payload.cover = albumCover.dataUrl;
    await API.post("album-cover", payload);
    closeAlbumCover();
    await refreshAfterEdit();
    toast(
      albumCover.action === "remove"
        ? "Обложка альбома сброшена"
        : "Обложка альбома сохранена в приложении"
    );
  } catch (error) {
    toast(`Не удалось записать обложку: ${error.message}`);
  } finally {
    el.coverSave.disabled = false;
    el.coverSave.textContent = "Сохранить";
  }
}

async function saveEditor(event) {
  event.preventDefault();
  const tracks = state.editTracks || [];
  if (!tracks.length) return;
  const multi = tracks.length > 1;
  const payload = {};
  el.editFields.querySelectorAll("input").forEach((input) => {
    const key = input.dataset.key;
    const value = input.value;
    if (!multi) {
      payload[key] = value;
      return;
    }
    const baseline = state.editBaseline[key];
    if ((baseline === null ? "" : baseline) !== value) payload[key] = value;
  });
  if (multi && !Object.keys(payload).length && state.editCover.action === "keep") {
    toast("Ничего не изменено");
    return;
  }
  payload.cover_action = state.editCover.action;
  if (!multi) payload.apply_to_album = state.editCover.action === "set" && el.editCoverAlbum.checked;
  if (state.editCover.action === "set" && state.editCover.dataUrl) {
    payload.cover = state.editCover.dataUrl;
  }

  el.editSave.disabled = true;
  el.editSave.textContent = "Сохраняю…";
  let done = 0;
  let albumUpdated = 0;
  try {
    for (const track of tracks) {
      const response = await API.post(`tracks/${track.id}`, payload);
      albumUpdated += response.album_updated || 0;
      done += 1;
    }
    closeEditor();
    await refreshAfterEdit();
    toast(
      done > 1
        ? `Записано треков: ${done}`
        : albumUpdated
          ? `Обложка записана во весь альбом, файлов: ${albumUpdated + 1}`
          : "Метаданные записаны, файл сохранён"
    );
  } catch (error) {
    toast(`Не удалось сохранить: ${error.message}`);
  } finally {
    el.editSave.disabled = false;
    el.editSave.textContent = "Сохранить";
  }
}

async function refreshAfterEdit() {
  await loadTracks();
  if (state.view === "folder" && state.collection?.path) {
    await openFolder(state.collection.path, false);
  } else if (state.view === "album" && state.collection?.album) {
    await openAlbum(state.collection.album, state.collection.artist);
  }
  syncTransport();
  await refreshPlayingTrack();
}

async function refreshPlayingTrack() {
  if (!state.currentId) return;
  let fresh =
    state.tracks.find((track) => track.id === state.currentId) ||
    state.collection?.tracks?.find((track) => track.id === state.currentId) ||
    null;
  try {
    const data = await API.get(`tracks/${state.currentId}`);
    if (data.track) fresh = data.track;
  } catch (error) {
    /* fall back to the row we already know */
  }
  if (!fresh) return;
  const snapshot = [fresh.title, fresh.artist, fresh.album, fresh.cover_hash].join("\u0000");
  if (snapshot === state.nowSnapshot) return;
  updateNow(fresh);
}

/* ---------------------------------------------------------------- lyrics */
async function loadLyrics(trackId) {
  state.lyrics = null;
  state.lyricLines = [];
  state.lyricIndex = -1;
  state.followPauseUntil = 0;
  try {
    const data = await API.get(`lyrics/${trackId}`);
    state.lyrics = data.lyrics;
  } catch (error) {
    state.lyrics = null;
  }
  if (!state.lyrics && state.autoLyrics && !state.lyricsSkipped.has(trackId)) {
    el.npLyrics.innerHTML = '<div class="lyrics-empty">Ищу текст…</div>';
    try {
      const found = await API.post(`lyrics/${trackId}/fetch`, {});
      state.lyrics = found.lyrics;
    } catch (error) {
      state.lyricsSkipped.add(trackId);
    }
  }
  renderLyrics();
}

function lyricsHaveText() {
  return Boolean(
    state.lyrics && ((state.lyrics.synced || "").trim() || (state.lyrics.plain || "").trim())
  );
}

let lyricsAnimToken = 0;

function slideLeftIntoPlace(first) {
  const last = el.npLeft.getBoundingClientRect();
  const shift = first.left - last.left;
  if (Math.abs(shift) < 1 || !el.npLeft.animate) return;
  el.npLeft.getAnimations().forEach((animation) => animation.cancel());
  el.npLeft.animate(
    [{ transform: `translateX(${shift}px)` }, { transform: "translateX(0)" }],
    { duration: 420, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }
  );
}

async function applyLyricsVisibility(animated = true) {
  const hasText = lyricsHaveText();
  const shown = hasText && state.lyricsVisible;
  const wasShown = el.npBody.classList.contains("with-lyrics");

  el.npLyricsToggle.disabled = !hasText;
  setIcon(el.npLyricsToggle, state.lyricsVisible ? "eye" : "eye-off");

  if (shown === wasShown) return;

  const token = ++lyricsAnimToken;
  if (!animated) {
    el.npBody.classList.toggle("with-lyrics", shown);
    return;
  }

  if (!shown) {
    try {
      const fade = el.npRight.animate(
        [{ opacity: 1, transform: "translateX(0)" }, { opacity: 0, transform: "translateX(14px)" }],
        { duration: 200, easing: "ease", fill: "forwards" }
      );
      await fade.finished;
    } catch (error) {
      /* animation cancelled by a newer toggle */
    }
    if (token !== lyricsAnimToken) return;
    const first = el.npLeft.getBoundingClientRect();
    el.npBody.classList.remove("with-lyrics");
    slideLeftIntoPlace(first);
    return;
  }

  const first = el.npLeft.getBoundingClientRect();
  el.npBody.classList.add("with-lyrics");
  slideLeftIntoPlace(first);
  if (el.npRight.animate) {
    el.npRight.getAnimations().forEach((animation) => animation.cancel());
    el.npRight.animate(
      [{ opacity: 0, transform: "translateX(18px)" }, { opacity: 1, transform: "translateX(0)" }],
      { duration: 340, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }
    );
  }
}

function toggleLyrics() {
  state.lyricsVisible = !state.lyricsVisible;
  savePreference("ui.lyricsVisible", state.lyricsVisible ? "1" : "0");
  applyLyricsVisibility();
}

function savePreference(key, value) {
  API.post("settings", { key, value }).catch(() => {});
}

async function loadPreferences() {
  try {
    const data = await API.get("preferences");
    const prefs = data.preferences || {};
    if (prefs["ui.lyricsVisible"] !== undefined) {
      state.lyricsVisible = prefs["ui.lyricsVisible"] !== "0";
    }
    if (prefs["ui.autoLyrics"] !== undefined) {
      state.autoLyrics = prefs["ui.autoLyrics"] !== "0";
    }
    if (prefs["ui.accent"]) state.accent = prefs["ui.accent"];
    if (prefs["ui.base"]) state.base = prefs["ui.base"];
  } catch (error) {
    /* first launch: keep the defaults */
  }
  applyTheme();
  setIcon(el.npLyricsToggle, state.lyricsVisible ? "eye" : "eye-off");
  applyLyricsVisibility(false);
}

function renderLyrics() {
  const box = el.npLyrics;
  applyLyricsVisibility();
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
    box.innerHTML = '<div class="lyrics-spacer"></div>' +
      lines
        .map((line) => `<div class="lyric-line" data-time="${line.time}">${escapeHtml(line.text || "♪")}</div>`)
        .join("") +
      '<div class="lyrics-spacer"></div>';
    state.lyricIndex = -1;
    syncLyric();
  } else {
    box.innerHTML = `<div class="lyrics-plain">${escapeHtml(state.lyrics.plain || "")}</div>`;
  }
}

function scrollToLine(index, smooth = true) {
  const nodes = el.npLyrics.querySelectorAll(".lyric-line");
  const node = nodes[index];
  if (!node) return;
  const containerRect = el.npLyrics.getBoundingClientRect();
  const nodeRect = node.getBoundingClientRect();
  const delta = nodeRect.top - containerRect.top;
  const top = el.npLyrics.scrollTop + delta - (el.npLyrics.clientHeight - node.clientHeight) / 2;
  el.npLyrics.scrollTo({ top, behavior: smooth ? "smooth" : "auto" });
}

function syncLyric() {
  if (!state.lyricLines.length) return;
  const current = el.audio.currentTime;
  let index = 0;
  for (let i = 0; i < state.lyricLines.length; i += 1) {
    if (state.lyricLines[i].time <= current) index = i;
    else break;
  }
  if (index === state.lyricIndex) return;
  state.lyricIndex = index;
  el.npLyrics.querySelectorAll(".lyric-line").forEach((node, i) => {
    node.classList.toggle("active", i === index);
  });
  if (!el.nowplaying.hidden && Date.now() >= state.followPauseUntil) {
    scrollToLine(index);
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
  updateLyricsFormat();
  el.lyricsModal.hidden = false;
  requestAnimationFrame(() => el.lyricsText.focus());
}

function updateLyricsFormat() {
  const text = el.lyricsText.value;
  const timed = text.match(/^\[\d{1,3}:\d{1,2}(?:[.,]\d{1,3})?\]/gm) || [];
  const lines = text.split("\n").filter((line) => line.trim()).length;
  if (!lines) {
    el.lyricsFormat.textContent = "Можно вставить обычный текст или LRC — формат определится сам";
  } else if (timed.length) {
    el.lyricsFormat.textContent = `LRC: ${timed.length} строк с таймкодами — текст будет синхронизирован`;
  } else {
    el.lyricsFormat.textContent = `Обычный текст: ${lines} строк — без синхронизации`;
  }
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
  if (!(await askConfirm("Удалить текст?", "Текст будет удалён у этого трека."))) return;
  try {
    await API.del(`lyrics/${state.currentId}`);
    state.lyricsSkipped.add(state.currentId);
    closeLyricsEditor();
    await loadLyrics(state.currentId);
    toast("Текст удалён");
  } catch (error) {
    toast(`Не удалось удалить текст: ${error.message}`);
  }
}

async function findLyrics() {
  const trackId = state.currentId || state.editing?.id;
  if (!trackId) return;
  el.lyricsFind.disabled = true;
  el.lyricsFind.textContent = "Ищу…";
  try {
    const found = await API.post(`lyrics/${trackId}/fetch`, { force: true });
    state.lyrics = found.lyrics;
    state.lyricsSkipped.delete(trackId);
    el.lyricsText.value = found.lyrics.synced || found.lyrics.plain || "";
    renderLyrics();
    toast("Текст найден");
  } catch (error) {
    toast("Текст не найден");
  } finally {
    el.lyricsFind.disabled = false;
    el.lyricsFind.textContent = "Найти в интернете";
  }
}

/* ---------------------------------------------------------------- wiring */
el.view.addEventListener("click", async (event) => {
  if (event.target.id === "online-go") {
    await searchOnline();
    return;
  }
  const download = event.target.closest("[data-download]");
  if (download) {
    await downloadOnline(download.dataset.download, download);
    return;
  }
  const add = event.target.closest(".row-add");
  if (add) {
    event.stopPropagation();
    openAddMenu(add, Number(add.dataset.add));
    return;
  }
  if (event.target.id === "playlist-new") {
    createPlaylistPrompt();
    return;
  }
  if (event.target.id === "playlist-play") {
    if (state.queue.length) playTrack(state.queue[0]);
    return;
  }
  if (event.target.id === "playlist-delete" && state.playlist) {
    const playlistName = state.playlist.playlist.name;
    if (await askConfirm(`Удалить плейлист «${playlistName}»?`, "Треки останутся в библиотеке.")) {
      await API.del(`playlists/${state.playlist.playlist.id}`);
      state.playlist = null;
      renderPlaylists();
    }
    return;
  }
  const playlistRow = event.target.closest("[data-playlist]");
  if (playlistRow) {
    openPlaylist(Number(playlistRow.dataset.playlist));
    return;
  }
  if (event.target.id === "collection-back") {
    await folderBack();
    return;
  }
  if (event.target.id === "album-cover") {
    openAlbumCover();
    return;
  }
  if (event.target.id === "folder-new") {
    await createFolder();
    return;
  }
  if (event.target.id === "folders-add") {
    await addFolder();
    return;
  }
  if (event.target.id === "folder-upload") {
    await uploadTracks();
    return;
  }
  const subfolder = event.target.closest("[data-subfolder]");
  if (subfolder) {
    event.stopPropagation();
    await openFolder(subfolder.dataset.subfolder);
    return;
  }
  const albumCard = event.target.closest(".album-card");
  if (albumCard) {
    await openAlbum(albumCard.dataset.album, albumCard.dataset.artist);
    return;
  }
  const rescan = event.target.closest("[data-rescan]");
  if (rescan) {
    event.stopPropagation();
    API.post("scan", { path: rescan.dataset.rescan }).then(pollScan).catch(() => {});
    return;
  }
  const open = event.target.closest(".row-open");
  if (open) {
    event.stopPropagation();
    API.post("reveal", { path: open.dataset.open }).catch((error) => toast(`Не удалось открыть: ${error.message}`));
    return;
  }
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
  const collectionRow = event.target.closest(".row[data-id]");
  if (collectionRow && (state.view === "folder" || state.view === "album")) {
    selectTrack(Number(collectionRow.dataset.id), event);
    return;
  }
  const row = event.target.closest(".row");
  if (!row) return;
  if (row.dataset.folder) {
    state.folderStack = [];
    await openFolder(row.dataset.folder);
    return;
  }
  if (row.dataset.id) {
    const id = Number(row.dataset.id);
    if (id === state.currentId) {
      togglePlay();
      return;
    }
    playTrack(id);
  }
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
el.npExit.addEventListener("click", closeNowPlaying);
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

el.editCoverPick.addEventListener("click", () => el.editCoverFile.click());
el.editCoverFile.addEventListener("change", () => {
  const file = el.editCoverFile.files && el.editCoverFile.files[0];
  if (!file) return;
  if (file.size > 12_000_000) {
    toast("Файл больше 12 МБ — уменьшите обложку");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = String(reader.result);
    state.editCover = { action: "set", dataUrl };
    setEditCoverPreview(dataUrl);
    el.editCoverHint.textContent = file.name;
  };
  reader.readAsDataURL(file);
});
el.editCoverRemove.addEventListener("click", () => {
  state.editCover = { action: "remove", dataUrl: null };
  setEditCoverPreview("");
  el.editCoverHint.textContent = "Обложка будет удалена из файла";
});
el.editCoverFind.addEventListener("click", findCoverOnline);
el.editCoverResults.addEventListener("click", (event) => {
  const choice = event.target.closest("[data-key]");
  if (choice) pickOnlineCover(choice.dataset.key, choice);
});

el.coverFind.addEventListener("click", findAlbumCover);
el.coverResults.addEventListener("click", (event) => {
  const choice = event.target.closest("[data-key]");
  if (choice) pickAlbumCover(choice.dataset.key, choice);
});
el.coverPick.addEventListener("click", () => el.coverFile.click());
el.coverRemove.addEventListener("click", () => {
  if (!state.albumCover) return;
  state.albumCover.action = "remove";
  state.albumCover.dataUrl = null;
  setCoverDialogPreview("");
  el.coverResults.querySelectorAll(".cover-choice").forEach((node) => node.classList.remove("active"));
  el.coverHint.textContent = "Обложка вернётся к картинке из файлов";
});
el.coverFile.addEventListener("change", () => {
  const file = el.coverFile.files && el.coverFile.files[0];
  if (!file || !state.albumCover) return;
  if (file.size > 12_000_000) {
    toast("Файл больше 12 МБ — уменьшите обложку");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = String(reader.result);
    state.albumCover.action = "set";
    state.albumCover.dataUrl = dataUrl;
    setCoverDialogPreview(dataUrl);
    el.coverResults.querySelectorAll(".cover-choice").forEach((node) => node.classList.remove("active"));
    el.coverHint.textContent = file.name;
  };
  reader.readAsDataURL(file);
});
el.coverSave.addEventListener("click", saveAlbumCover);
el.coverCancel.addEventListener("click", closeAlbumCover);
el.coverClose.addEventListener("click", closeAlbumCover);
el.coverModal.addEventListener("click", (event) => {
  if (event.target === el.coverModal) closeAlbumCover();
});

el.openSettings.addEventListener("click", openSettings);
el.settingsClose.addEventListener("click", closeSettings);
el.settingsDone.addEventListener("click", closeSettings);
el.settingsModal.addEventListener("click", (event) => {
  if (event.target === el.settingsModal) closeSettings();
});
el.settingAutoLyrics.addEventListener("change", () => setAutoLyrics(el.settingAutoLyrics.checked));
el.accentChoices.addEventListener("click", (event) => {
  const button = event.target.closest("[data-accent]");
  if (!button) return;
  state.accent = button.dataset.accent;
  savePreference("ui.accent", state.accent);
  applyTheme();
});
el.baseChoices.addEventListener("click", (event) => {
  const button = event.target.closest("[data-base]");
  if (!button) return;
  state.base = button.dataset.base;
  savePreference("ui.base", state.base);
  applyTheme();
});
el.settingGeniusSave.addEventListener("click", saveGeniusToken);
el.settingGenius.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    saveGeniusToken();
  }
});
el.settingCacheClear.addEventListener("click", clearThumbCache);
el.settingLyricsClear.addEventListener("click", clearLyricsCache);
el.settingDataOpen.addEventListener("click", openDataFolder);
el.editModal.addEventListener("click", (event) => {
  if (event.target === el.editModal) closeEditor();
});

el.askOk.addEventListener("click", () => {
  closeAsk(state.askMode === "text" ? el.askInput.value.trim() : true);
});
el.askCancel.addEventListener("click", () => {
  closeAsk(state.askMode === "text" ? null : false);
});
el.askInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    el.askOk.click();
  }
});
el.askModal.addEventListener("click", (event) => {
  if (event.target === el.askModal) closeAsk(state.askMode === "text" ? null : false);
});

el.selectionEdit.addEventListener("click", () => openEditorFor([...state.selection]));
el.selectionPlay.addEventListener("click", () => {
  const ids = [...state.selection];
  if (!ids.length) return;
  state.queue = ids;
  state.queueIndex = 0;
  state.history = [];
  playTrack(ids[0]);
});
el.selectionClear.addEventListener("click", () => {
  state.selection = new Set();
  state.lastSelected = null;
  updateSelection();
});
el.selectionDelete.addEventListener("click", async () => {
  const ids = [...state.selection];
  if (!ids.length) return;
  const agreed = await askConfirm(
    "Удалить треки?",
    `Файлы будут перемещены в корзину, записи исчезнут из библиотеки. Выбрано: ${ids.length}.`
  );
  if (!agreed) return;
  try {
    const result = await API.post("delete-tracks", { ids });
    toast(`Удалено: ${result.removed}`);
    state.selection = new Set();
    state.lastSelected = null;
    if (state.view === "folder" && state.collection?.path) {
      await openFolder(state.collection.path, false);
    } else if (state.view === "album" && state.collection?.album) {
      await openAlbum(state.collection.album, state.collection.artist);
    }
    await loadTracks();
  } catch (error) {
    toast("Не удалось удалить треки");
  }
});

el.npLyricsToggle.addEventListener("click", toggleLyrics);
el.lyricsText.addEventListener("input", updateLyricsFormat);
el.uploadFiles.addEventListener("change", async () => {
  const files = [...el.uploadFiles.files];
  el.uploadFiles.value = "";
  if (files.length) await handleUpload(files);
});
loadPreferences();

window.addEventListener("focus", () => {
  refreshCurrentView();
});
setInterval(() => {
  refreshCurrentView();
}, 8000);

el.npLyricsEdit.addEventListener("click", openLyricsEditor);
el.lyricsForm.addEventListener("submit", saveLyrics);
el.lyricsClose.addEventListener("click", closeLyricsEditor);
el.lyricsCancel.addEventListener("click", closeLyricsEditor);
el.lyricsClear.addEventListener("click", clearLyrics);
el.lyricsFind.addEventListener("click", findLyrics);
el.lyricsModal.addEventListener("click", (event) => {
  if (event.target === el.lyricsModal) closeLyricsEditor();
});

el.npLyrics.addEventListener("wheel", () => {
  state.followPauseUntil = Date.now() + 3000;
}, { passive: true });
el.npLyrics.addEventListener("touchmove", () => {
  state.followPauseUntil = Date.now() + 3000;
}, { passive: true });
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
  if (event.code === "KeyM") { el.audio.muted = !el.audio.muted; setIcon(el.mute, el.audio.muted ? "mute" : "volume"); setIcon(el.npMute, el.audio.muted ? "mute" : "volume"); }
  if (event.code === "KeyL") toggleLyrics();
  if (event.code === "Escape") {
    if (!el.askModal.hidden) closeAsk(state.askMode === "text" ? null : false);
    else if (!el.settingsModal.hidden) closeSettings();
    else if (!el.coverModal.hidden) closeAlbumCover();
    else if (!el.lyricsModal.hidden) closeLyricsEditor();
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

el.audio.volume = 0.8;

loadTracks();
