/** @type {import('tailwindcss').Config} */
module.exports = {
  prefix: 'lmk-',
  content: ["./src/**/*.tsx"],
  theme: {
    colors: {
      font: 'var(--jp-ui-font-color0)',
      link: 'var(--jp-mirror-editor-variable-2-color)',
      editorBorder: 'var(--jp-cell-editor-border-color)',
      success: 'var(--jp-success-color0)',
      error: 'var(--jp-error-color0)',
      warn: 'var(--jp-warn-color0)',
      cellBg: 'var(--jp-layout-color1)',
      bgLight: 'var(--jp-layout-color2)',
      transparent: 'transparent',
    },
    fontFamily: {
      jupyter: 'var(--jp-ui-font-family)',
    },
    extend: {},
  },
  plugins: [],
};
