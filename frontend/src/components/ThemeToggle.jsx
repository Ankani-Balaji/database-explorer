import { useEffect, useState } from "react";

const KEY = "ifm_theme";

const stored = () => {
  try { return localStorage.getItem(KEY); } catch { return null; }
};
const systemTheme = () =>
  window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";

export default function ThemeToggle({ className = "" }) {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || stored() || systemTheme());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    try { localStorage.setItem(KEY, next); } catch { /* private mode: just don't remember */ }
    setTheme(next);
  };

  const label = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
  return (
    <button type="button" className={`theme-toggle ${className}`} onClick={toggle} title={label} aria-label={label}>
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}
