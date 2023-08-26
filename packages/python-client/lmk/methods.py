from lmk.instance import Instance, get_instance


extra_names = ["channels"]


def _is_valid_name(name: str) -> bool:
    if name in extra_names:
        return True
    if name.startswith("_"):
        return False
    if not hasattr(Instance, name):
        return False
    if isinstance(getattr(Instance, name), property):
        return False
    return True


__all__ = [name for name in dir(Instance) + extra_names if _is_valid_name(name)]


def __getattr__(name: str):
    if not _is_valid_name(name):
        raise AttributeError(name)
    instance = get_instance()
    return getattr(instance, name)
