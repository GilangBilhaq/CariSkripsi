"use client";

import { useSyncExternalStore } from "react";

const KEY = "cariskripsi.penilai";

// Cadangan bila localStorage diblokir browser (mode privat, dsb.): nama hanya bertahan selama tab terbuka.
let memoryValue = "";
const listeners = new Set<() => void>();

function read(): string {
  try {
    return localStorage.getItem(KEY) ?? memoryValue;
  } catch {
    return memoryValue;
  }
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  window.addEventListener("storage", onChange); // perubahan dari tab lain
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

function write(value: string) {
  memoryValue = value;
  try {
    localStorage.setItem(KEY, value);
  } catch {
    /* abaikan: memoryValue tetap dipakai */
  }
  listeners.forEach((notify) => notify());
}

/**
 * Nama penilai relevansi, disimpan di browser supaya tidak perlu diketik ulang.
 * Akun admin hanya satu, jadi nama inilah yang membedakan Penilai 1 dan Penilai 2.
 */
export function useJudgeName(): [string, (name: string) => void] {
  const name = useSyncExternalStore(subscribe, read, () => "");
  return [name, write];
}
