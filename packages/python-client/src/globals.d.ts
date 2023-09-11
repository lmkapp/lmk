declare module "*.css" {
  const content: Record<string, string>;
  export default content;
}

declare const IPython: {
  notebook: {
    notebook_name: string;
  };
};

declare const google:
  | undefined
  | {
      colab: {
        kernel: {
          invokeFunction: (name: string, args: string[]) => Promise<void>;
        };
      };
    };
