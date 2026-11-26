const TOKEN = new URLSearchParams(location.search).get("t") || "";

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-Token": TOKEN, ...(options.headers || {}) },
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text || response.statusText;
    try {
      const parsed = JSON.parse(text);
      if (parsed && parsed.error) message = parsed.error;
    } catch (error) {
      /* plain text or empty body */
    }
    throw new Error(message);
  }
  return response.json();
}

const API = {
  get(path, params = {}) {
    const url = new URL(`/api/${path}`, location.origin);
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
    }
    return request(url.pathname + url.search);
  },
  post(path, body = {}) {
    return request(`/api/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },
  del(path) {
    return request(`/api/${path}`, { method: "DELETE" });
  },
  media(id) {
    return `/media/${id}?t=${TOKEN}`;
  },
  thumb(hash, size = 320) {
    return `/thumb/${hash}?size=${size}&t=${TOKEN}`;
  },
};
