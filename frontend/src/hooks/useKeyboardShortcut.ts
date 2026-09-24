import { useEffect } from "react";

export function useKeyboardShortcut(
  key: string,
  callback: (e: KeyboardEvent) => void,
  options: { ctrlOrCmd?: boolean; shift?: boolean; alt?: boolean; ignoreInInputs?: boolean } = {
    ignoreInInputs: true,
  }
) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (options.ignoreInInputs) {
        const target = e.target as HTMLElement | null;
        if (
          target &&
          (target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.isContentEditable)
        ) {
          return;
        }
      }

      const matchKey = e.key.toLowerCase() === key.toLowerCase();
      const matchCtrl = options.ctrlOrCmd ? e.ctrlKey || e.metaKey : true;
      const matchShift = options.shift ? e.shiftKey : true;
      const matchAlt = options.alt ? e.altKey : true;

      if (matchKey && matchCtrl && matchShift && matchAlt) {
        e.preventDefault();
        callback(e);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [key, callback, options]);
}
