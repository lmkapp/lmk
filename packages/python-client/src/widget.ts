import { DOMWidgetView } from "@jupyter-widgets/base";
import { createElement } from "react";
import ReactDOM from "react-dom";

import Widget from "./components/Widget";
import { WidgetViewProvider } from "./lib/widget-model";

export class LMKView extends DOMWidgetView {
  render() {
    const component = createElement(WidgetViewProvider, {
      model: this.model,
      children: [createElement(Widget)],
    });

    ReactDOM.render(component, this.el);
  }
}
