/** @type {import('tailwindcss').Config} */
module.exports = {
  prefix: 'lmk-',
  content: ["./src/**/*.tsx"],
  theme: {
    colors: {
      font: 'var(--colab-primary-text-color, var(--jp-ui-font-color0, rgba(0, 0, 0, 1)))',
      link: 'var(--jp-mirror-editor-variable-2-color, #05a)',
      editorBorder: 'var(--colab-border-color, var(--jp-cell-editor-border-color, #e0e0e0))',
      success: 'var(--jp-success-color0, #1b5e20)',
      error: 'var(--jp-error-color0, #b71c1c)',
      warn: 'var(--jp-warn-color0, #e65100)',
      cellBg: 'var(--colab-secondary-surface-color, var(--jp-layout-color1, #f8f8f8))',
      bgLight: 'var(--colab-highlighted-surface-color, var(--jp-layout-color2, #eeeeee))',
      transparent: 'transparent',
    },
    fontFamily: {
      jupyter: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol'`,
    },
    fontSize: {
      sm: '90%',
      base: '100%',
      md: '100%',
      lg: '130%',
      xl: '150%',
      '2xl': '180%',
      '3xl': '200%',
    },
    extend: {},
  },
  plugins: [],
};
