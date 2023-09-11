import { useWidgetModelEvent } from "../lib/widget-model";

export function useColabSupport(): void {
  useWidgetModelEvent("msg:custom", async (_, event) => {
    console.log("Handling custom event", event);
    if (event?.type === "collab-update" && typeof google !== "undefined") {
      console.log("Invoking sync function");
      await google.colab.kernel.invokeFunction("lmk.widget.sync", []);
    }
  });
}
