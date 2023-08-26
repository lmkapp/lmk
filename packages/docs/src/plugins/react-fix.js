module.exports = function(context, options) {
  return {
    name: 'fix-react-plugin',
    configureWebpack(config, isServer, utils) {
      return {
        resolve: {
          alias: {
            'react/jsx-runtime': 'react/jsx-runtime.js',
            'react/jsx-dev-runtime': 'react/jsx-dev-runtime.js',
          }
        }
      };
    }
  };
}
