const path = require('path');
const tailwindcss = require('tailwindcss');

const pkg = require('./package.json');

const version = pkg.version;

const name = pkg.name;

function rules(type) {
  return [
    {
      test: /\.tsx?$/,
      use: [
        {
          loader: 'ts-loader',
          options: {
            configFile: 'tsconfig.build.json'
          }
        }
      ]
    },
    { test: /\.js$/, loader: 'source-map-loader' },
    {
      test: /tailwind\.css$/,
      use: [
        'style-loader',
        'css-loader',
        {
          loader: 'postcss-loader',
          options: {
            postcssOptions: {
              plugins: [
                'postcss-preset-env',
                tailwindcss({
                  config: path.resolve(__dirname, `tailwind-${type}.config.js`)
                }),
              ]
            }
          }
        }
      ],
    },
    {
      test: /\.css$/,
      use: ['style-loader', 'css-loader'],
      exclude: /tailwind\.css$/
    },
    {
      test: /\.svg$/,
      type: 'asset/source',
    }
  ];
}

// Packages that shouldn't be bundled but loaded at runtime
const externals = ['@jupyter-widgets/base'];

const resolve = {
  // Add '.ts' and '.tsx' as resolvable extensions.
  extensions: [".webpack.js", ".web.js", ".ts", ".js", ".tsx"]
};

const isProduction = process.env.NODE_ENV === 'production';

const mode = isProduction ? 'production' : 'development';

const devtool = isProduction ? false : 'source-map';

module.exports = [
  /**
   * Notebook extension
   *
   * This bundle only contains the part of the JavaScript that is run on load of
   * the notebook.
   */
  {
    mode,
    entry: './src/extension.ts',
    output: {
      filename: 'jupyter-widget.js',
      path: path.resolve(__dirname, 'lmk', 'jupyter', 'nbextension', '@lmkapp'),
      library: name,
      libraryTarget: 'amd',
      publicPath: '',
    },
    module: { rules: rules('nbextension') },
    devtool,
    externals,
    resolve,
    optimization: {
      minimize: false
   },
  },

  /**
   * Embeddable lmk bundle
   *
   * This bundle is almost identical to the notebook extension bundle. The only
   * difference is in the configuration of the webpack public path for the
   * static assets.
   *
   * The target bundle is always `dist/index.js`, which is the path required by
   * the custom widget embedder.
   */
  {
    mode,
    entry: './src/index.ts',
    output: {
        filename: 'index.js',
        path: path.resolve(__dirname, 'dist'),
        libraryTarget: 'amd',
        library: name,
        publicPath: 'https://unpkg.com/lmk@' + version + '/dist/'
    },
    devtool,
    module: { rules: rules('nbextension') },
    externals,
    resolve,
    optimization: {
      minimize: false
   },
  },
  // This pre-builds the extension JS so we can use
  // custom webpack rules like preprocessing CSS
  {
    mode,
    entry: './src/plugin.ts',
    output: {
        filename: 'plugin.js',
        path: path.resolve(__dirname, 'dist'),
        libraryTarget: 'commonjs2',
        publicPath: ''
    },
    devtool,
    module: { rules: rules('labextension') },
    externals,
    resolve,
    optimization: {
      minimize: false
   },
  },

];
