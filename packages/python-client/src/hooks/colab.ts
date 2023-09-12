import { useEffect } from "react";
import { useWidgetModelState } from "../lib/widget-model";

export interface UseColabSupportArgs {
  setRequiresReload: (requiresReload: boolean) => void;
}

export function useColabSupport({
  setRequiresReload,
}: UseColabSupportArgs): void {
  const [notebookName, setNotebookName] = useWidgetModelState("notebook_name");

  useEffect(() => {
    if (typeof google === 'undefined') {
      return;
    }

    const ivl = setInterval(() => {
      if (document.visibilityState === "hidden") {
        return;
      }
      const element = document.querySelector(
        "#doc-name"
      ) as HTMLInputElement | null;
      console.log('ELEMENT', element);
      if (element === null) {
        return;
      }
      if (notebookName === element.value) {
        return;
      }
      setNotebookName(element.value);
    }, 2000);

    return () => {
      clearInterval(ivl);
    };
  }, [notebookName]);

  // This would be the ideal way to trigger syncing (well, other than just
  // not having to it at all of course), but unfortunately it doesn't work
  // correctly. Falling back to using an interval (below) :(
  // useWidgetModelEvent("msg:custom", async (_, event) => {
  //   if (event?.type === "colab-update" && typeof google !== "undefined") {
  //     await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
  //   }
  // });

  useEffect(() => {
    if (typeof google === "undefined") {
      return;
    }

    const ivl = setInterval(async () => {
      if (document.visibilityState === "hidden") {
        return;
      }
      try {
        await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
        setRequiresReload(false);
      } catch (error: any) {
        if (error?.toString()?.includes('code cell must be re-executed to allow runtime access')) {
          setRequiresReload(true);
        }
      }
    }, 2000);

    return () => {
      clearInterval(ivl);
    };
  }, []);
}
