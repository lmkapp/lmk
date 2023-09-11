import { useEffect, useState } from "react";
import { useWidgetModelEvent } from "../lib/widget-model";

export function useColabSupport(): void {
  const [dirty, setDirty] = useState(0);

  useWidgetModelEvent("msg:custom", async (_, event) => {
    // console.log("Handling custom event", event, typeof google);
    if (event?.type === "colab-update" && typeof google !== "undefined") {
      setDirty((val) => val + 1);
    }
  });

  useEffect(() => {
    if (typeof google === 'undefined') {
      return;
    }

    const ivl = setInterval(async () => {
      console.log('dirty', dirty);
      if (dirty > 0) {
        await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
        setDirty((val) => val - 1);
      } 
    }, 500);

    return () => { clearInterval(ivl) };
  }, []);
}
