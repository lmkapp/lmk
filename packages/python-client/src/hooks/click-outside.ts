import { useRef, useEffect } from "react";

export function useClickOutside<E extends HTMLElement>(
  enabled: boolean,
  handleClickOutside: () => void
): React.RefObject<E> {
  const ref = useRef<E>(null);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const handleClick = (evt) => {
      if (ref.current && !ref.current.contains(evt.target)) {
        handleClickOutside();
      }
    };

    document.addEventListener("mousedown", handleClick);
    return () => {
      document.removeEventListener("mousedown", handleClick);
    };
  }, [enabled, ref.current, handleClickOutside]);

  return ref;
}
