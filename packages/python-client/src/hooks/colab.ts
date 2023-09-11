import { useEffect } from "react";

export function useColabSupport(): void {
  useEffect(() => {
    if (!google) {
      return;
    }

    const ivl = setInterval(async () => {
      await google!.colab.kernel.invokeFunction("lmk.widget.sync", []);
    }, 1000);

    return () => {
      clearInterval(ivl);
    };
  }, []);
}
