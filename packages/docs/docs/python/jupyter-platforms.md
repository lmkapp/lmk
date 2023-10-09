---
sidebar_position: 2
---
# Support for Jupyter Platforms

There are many plaftorms that support Jupyter notebooks or their own flavor of them. We want to make LMK as universal as possible, so over time we aim to implement full support for as many of these platforms as possible. The table below shows the current state of support for various platforms we're aware of.

This list is incomplete; if you would like support for a platform that you see is missing or have tried to use LMK on a new platform and encountered an issue, please open an [issue on Github](https://github.com/lmkapp/lmk/issues/new). We will try to keep any relevant Github issue links updated in this table where relevant so you can avoid creating a duplicate, but it's always worth searching to see if there's an existing issue before creating a new one.

✅ = Tested, expected to be working

❓ = Untested

❌ = Not working

| Platform          | Status    | Notes     |
| ----------------- | --------- | --------- |
| Jupyter Notebooks |    ✅     | There is automated testing in place for major versions 6 and 7 of `notebook`. Earlier versions may work, but have not been tested. |
| Jupyter Lab       |    ✅     | There is automated testing in place for major versions 3 and 4 of `jupyterlab`. Major versions 2 and earlier are not supported. |
| Google Colab     |    ✅     | Tested manually as of 9/15/2023. Colab is supported but requires a few hacks and is not quite as good of an experience as regular Jupyter Notebooks or Lab. Colab notebooks with a local runtime do not work at all; this is likely true of all runtimes that aren't hosted colab runtimes. It's worth looking at again to see if we can potentially provide better support. If you are using LMK with Google Colab, please comment or add a thumbs up to the [Github issue](https://github.com/lmkapp/lmk/issues/1) to indicate you'd like better support. |
| VSCode (via [jupyter](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter) plugin) |  ✅  | Tested manually as of 9/15/2023 |
| Kaggle            |    ❓     |           |
| AWS Sagemaker     |    ❓     |           |
| Microsoft Azure Notebooks | ❓ | |
| Databricks        | ❌ | Databricks notebooks, while similar to Jupyter notebooks, are an entirely different platform, and at the moment do not appear to support custom widgets. It doesn't appear feasible to implement support for Databricks without them supporting some sort of custom notebook widgets first. |
