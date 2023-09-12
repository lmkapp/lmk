import { useWidgetModelEvent } from "../lib/widget-model";

export function useColabSupport(): void {
  useWidgetModelEvent("msg:custom", async (_, event) => {
    // console.log("Handling custom event", event, typeof google);
    if (event?.type === "colab-update" && typeof google !== "undefined") {
      // await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
      await new Promise((resolve) => setTimeout(resolve, 500));
      console.log('Invoking sync function');
      await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
      // setDirty((val) => val + 1);
    }
  });

  // useEffect(() => {
  //   if (typeof google === 'undefined') {
  //     return;
  //   }

  //   const ivl = setInterval(() => {
  //     google.colab.kernel.invokeFunction("lmk.widget.sync", []);
  //   }, 2000);

  //   return () => { clearInterval(ivl) };
  // }, []);
}
