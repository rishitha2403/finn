import { useEffect, useState } from "react";

const PREFIX = "finn:";

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    return;
  }
}

export function useStored(key, fallback) {
  const [v, setV] = useState(() => read(key, fallback));
  useEffect(() => {
    write(key, v);
  }, [key, v]);
  return [v, setV];
}

export function lastVisit() {
  return read("lastVisit", null);
}

export function markVisit() {
  const prev = read("thisVisit", null);
  const now = Date.now();
  if (!prev || now - prev > 30 * 60 * 1000) {
    write("lastVisit", prev);
    write("thisVisit", now);
  }
  return read("lastVisit", null);
}
