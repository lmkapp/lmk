import { useWidgetModelEvent } from "../lib/widget-model";

export function useColabSupport(): void {
  useWidgetModelEvent("msg:custom", async (_, event) => {
    console.log("Handling custom event", event, typeof google);
    if (event?.type === "colab-update" && typeof google !== "undefined") {
      console.log("Invoking sync function");
      await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
    }
  });
}
