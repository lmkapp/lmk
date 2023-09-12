import { useEffect } from "react";

export function useColabSupport(): void {
  // does not work :(
  // useWidgetModelEvent("msg:custom", async (_, event) => {
  //   // console.log("Handling custom event", event, typeof google);
  //   if (event?.type === "colab-update" && typeof google !== "undefined") {
  //     await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
  //     // setDirty((val) => val + 1);
  //   }
  // });

  useEffect(() => {
    if (typeof google === 'undefined') {
      return;
    }

    const ivl = setInterval(() => {
      google.colab.kernel.invokeFunction("lmk.widget.sync", []);
    }, 2000);

    return () => { clearInterval(ivl) };
  }, []);
}
