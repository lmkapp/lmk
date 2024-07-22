from lmk.process import exc


MAPPING = {
    "CRITICAL": 50,
    "FATAL": 50,
    "ERROR": 40,
    "WARN": 30,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}


def get_log_level(log_level: str) -> int:
    """ """
    values = set(MAPPING.values())

    if log_level.isdigit():
        log_level_int = int(log_level)
        if log_level_int not in values:
            raise exc.InvalidLogLevel(log_level)
        return log_level_int

    out_log_level = log_level.strip().upper()
    if out_log_level not in MAPPING:
        raise exc.InvalidLogLevel(log_level)

    return MAPPING[out_log_level]
