/** @type {import('tailwindcss').Config} */
module.exports = {
  prefix: 'lmk-',
  content: ["./src/**/*.tsx"],
  theme: {
    colors: {
      font: 'rgba(0, 0, 0, 1)',
      link: '#05a',
      editorBorder: '#e0e0e0',
      success: '#1b5e20',
      error: '#b71c1c',
      warn: '#e65100',
      cellBg: '#f8f8f8',
      bgLight: '#eeeeee',
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
