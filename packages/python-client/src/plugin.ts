import { IJupyterWidgetRegistry } from "@jupyter-widgets/base";
import { Application, IPlugin } from "@lumino/application";
import { Widget } from "@lumino/widgets";

import { LMKModel } from "./lib/widget-model";
import { LMKView } from "./widget";
import { MODULE_NAME, MODULE_VERSION } from "./version";

const EXTENSION_ID = "lmk-jupyter:plugin";

const lmkPlugin: IPlugin<Application<Widget>, void> = {
  id: EXTENSION_ID,
  requires: [IJupyterWidgetRegistry],
  activate: activateWidgetExtension,
  autoStart: true,
} as unknown as IPlugin<Application<Widget>, void>;

export default lmkPlugin;

/**
 * Activate the widget extension.
 */
function activateWidgetExtension(
  app: Application<Widget>,
  registry: IJupyterWidgetRegistry
): void {
  registry.registerWidget({
    name: MODULE_NAME,
    version: MODULE_VERSION,
    exports: { LMKView, LMKModel },
  });
}
