---
sidebar_position: 3
---
# Python API

The methods and classes documented here only comprise a portion of all of the functionality of the ``lmk`` package, but these were chosen based on the pieces most likely to be useful to users of the package. You may not have any need for using the python API directly at all, as it's not required. It is expected that most users will mainly use the Jupyter and CLI integrations to monitor jupyter notebooks and command line processes respectively, in which case there's no need to call any of these functions directly.

## Top-level API functions

The following methods are available at the top level of the `lmk` module, and allow you to perform basic operations with LMK manually such as authenticating and sending notifications.

@pydoc lmk.instance.Instance.notify

@pydoc lmk.instance.Instance.logged_in

@pydoc lmk.instance.Instance.login

@pydoc lmk.instance.Instance.logout

@pydoc lmk.instance.Instance.list_notification_channels

@pydoc lmk.instance.Instance.create_session

@pydoc lmk.instance.Instance.session_connect

@pydoc lmk.instance.Instance.end_session

@pydoc lmk.instance.Channels

@pydoc lmk.utils.ws.WebSocket
