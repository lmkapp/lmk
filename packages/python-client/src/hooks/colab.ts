import { useWidgetModelEvent } from "../lib/widget-model";

export function useColabSupport(): void {
  useWidgetModelEvent("msg:custom", async (_, event) => {
    // console.log("Handling custom event", event, typeof google);
    if (event?.type === "colab-update" && typeof google !== "undefined") {
      console.log('Invoking sync function');
      try {
        await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
      } catch (error) {
        console.error('ERROR1', error);
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
      console.log('Invoking sync function again');
      try {
        await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
      } catch (error) {
        console.error('ERROR2', error);
      }
      console.log('Invoked twice');
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
