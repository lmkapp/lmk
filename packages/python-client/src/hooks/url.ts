import { useEffect } from "react";
import { useWidgetModelState } from "../lib/widget-model";

// Slight hack for jupyterlab--for some reason it's easy to get into
// a state where I have a notebook open but the URL is just `/lab`,
// which won't lead me to the actual notebook if I click the link.
// This function basically checks if the URL is changing to something
// that is almost the same as the old URL except has only a portion
// of the path name, and skips the update if so.
function shouldUpdateUrl(oldUrl: string | null, newUrl: string): boolean {
  if (oldUrl === null) {
    return true;
  }
  if (oldUrl === newUrl) {
    return false;
  }

  const oldUrlObj = new URL(oldUrl);
  const newUrlObj = new URL(newUrl);
  if (
    oldUrlObj.host === newUrlObj.host &&
    oldUrlObj.protocol === newUrlObj.protocol &&
    oldUrlObj.pathname !== newUrlObj.pathname &&
    oldUrlObj.pathname.startsWith(newUrlObj.pathname)
  ) {
    return false;
  }
  return true;
}

export function useKeepUrlUpdated(enabled: boolean): void {
  const [url, setUrl] = useWidgetModelState("url");
  const windowUndefined = typeof window === "undefined";

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const ivl = setInterval(() => {
      if (windowUndefined) {
        return;
      }
      if (shouldUpdateUrl(url, window.location.href)) {
        setUrl(window.location.href);
      }
    }, 1000);

    return () => clearInterval(ivl);
  }, [url, windowUndefined, enabled]);
}
