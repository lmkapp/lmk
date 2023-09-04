import React from "react";
import utilStyles from "../css/utils.module.css";

interface CompatibleTool {
  name: string;
  Svg: React.ComponentType<React.ComponentProps<"svg">>;
}

const compatibleTools: CompatibleTool[] = [
  {
    name: "Jupyter",
    Svg: require("@site/static/img/jupyter.svg").default,
  },
  {
    name: "Colaboratory",
    Svg: require("@site/static/img/colaboratory.svg").default,
  },
  {
    name: "Terminal",
    Svg: require("@site/static/img/terminal.svg").default,
  },
];

export default function CompatibleTools() {
  return (
    <div className="mt-6 px-[100px] flex flex-col gap-6 pb-6">
      <h1 className="text-center">Works with your favorite tools</h1>
      <div className="flex flex-wrap w-full justify-between">
        {compatibleTools.map((tool, idx) => (
          <div key={idx} className="w-[200px] h-[200px]">
            <tool.Svg
              className={utilStyles.svgDropShadow}
              style={{ height: "100%", width: "100%" }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
