import importlib
from unittest.mock import patch

import lmk
from lmk.api_client import ApiClient
from lmk.instance import Channels


def test_import_no_requests():
    with patch.object(ApiClient, "call_api") as p:
        r = importlib.reload(lmk)
        r.channels

    p.assert_not_called()


def test_top_level_methods():
    assert isinstance(lmk.channels, Channels)
    assert callable(lmk.notify)
    assert callable(lmk.logged_in)
    assert callable(lmk.login)
    assert callable(lmk.logout)


def test_jupyter():
    assert lmk.jupyter.get_widget()
