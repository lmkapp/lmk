module.exports = function(context, options) {
  /** @type {import('@docusaurus/types').Plugin} */
  return {
    name: 'tailwind-plugin',
    configurePostCss: (options) => {
      options.plugins.push(require('tailwindcss'));
      options.plugins.push(require('autoprefixer'));
      return options;
    },
  };
}
