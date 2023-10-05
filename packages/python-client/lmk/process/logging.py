import logging

from lmk.process import exc


def get_log_level(log_level: str) -> int:
    """ """
    mapping = logging.getLevelNamesMapping()

    values = set(mapping.values())

    if log_level.isdigit():
        log_level_int = int(log_level)
        if log_level_int not in values:
            raise exc.InvalidLogLevel(log_level)
        return log_level_int

    out_log_level = log_level.strip().upper()
    if out_log_level not in mapping:
        raise exc.InvalidLogLevel(log_level)

    return mapping[out_log_level]
