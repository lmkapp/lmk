from lmk.jupyter.widget import get_widget


__all__ = ["set_monitoring_state", "set_log_level"]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(name)
    widget = get_widget()
    return getattr(widget, name)
