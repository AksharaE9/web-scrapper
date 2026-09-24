export type ThemeMode = "light" | "dark" | "system";
export type DensityMode = "comfortable" | "compact";

export function applyTheme(theme: ThemeMode) {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}
