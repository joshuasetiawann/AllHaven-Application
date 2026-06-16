"use client";

import { useEffect } from "react";
import { applyPrefs, loadPrefs } from "@/lib/prefs";

export function PreferenceHydrator() {
  useEffect(() => {
    applyPrefs(loadPrefs());
  }, []);

  return null;
}
