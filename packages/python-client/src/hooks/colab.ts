import { useEffect } from "react";

export interface UseColabSupportArgs {
  requiresReload: boolean;
  setRequiresReload: () => void;
}

export function useColabSupport({
  requiresReload,
  setRequiresReload,
}: UseColabSupportArgs): boolean {
  const googleDefined = typeof google !== "undefined";

  // Unfortunately, this is the only way that I can find to consistently update
  // the widget state in Colab. The problem stems from the fact that updating a widget's
  // state in a background thread in colab simply does not work; I tried to use an event-based
  // approach to this using the `msg:custom` event handler, but that didn't work either--likely
  // whatever issue affects syncing the widget state stems from the `comm` object, so sending
  // messages also doesn't work from a background thread. It's possible that a better solution
  // exists, though of course it's difficult to be 100% sure since colab isn't open source.
  // This project seems to be the current implementation of the custom widget manager, and it is
  // possible to install a custom one, so it's possible that something is possible there (though
  // I'm not hopeful because the issue seems to be on the kernel side--)
  useEffect(() => {
    if (!googleDefined || requiresReload) {
      return;
    }

    const ivl = setInterval(async () => {
      if (document.visibilityState === "hidden") {
        return;
      }
      try {
        await google!.colab.kernel.invokeFunction("lmk.widget.sync", []);
      } catch (error: any) {
        if (
          error
            ?.toString()
            ?.includes("code cell must be re-executed to allow runtime access")
        ) {
          setRequiresReload();
        } else if (
          error?.toString()?.includes("Function not found: lmk.widget.sync")
        ) {
          setRequiresReload();
        } else {
          throw error;
        }
      }
    }, 2000);

    return () => {
      clearInterval(ivl);
    };
  }, [requiresReload, googleDefined]);

  return !googleDefined;
}
