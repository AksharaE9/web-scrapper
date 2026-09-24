import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ThemeMode, DensityMode, applyTheme } from "../design/theme";

interface UiPrefsState {
  theme: ThemeMode;
  density: DensityMode;
  railCollapsed: boolean;
  setTheme: (theme: ThemeMode) => void;
  setDensity: (density: DensityMode) => void;
  toggleRail: () => void;
}

export const useUiPrefs = create<UiPrefsState>()(
  persist(
    (set) => ({
      theme: "dark",
      density: "comfortable",
      railCollapsed: false,
      setTheme: (theme) => {
        applyTheme(theme);
        set({ theme });
      },
      setDensity: (density) => set({ density }),
      toggleRail: () => set((s) => ({ railCollapsed: !s.railCollapsed })),
    }),
    {
      name: "leadcore_ui_prefs",
      onRehydrateStorage: () => (state) => {
        if (state) {
          applyTheme(state.theme);
        }
      },
    }
  )
);
