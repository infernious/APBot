import re
from typing import Union

time_regex = re.compile(r"(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"s": 1, "m": 60, "h": 60 * 60, "d": 60 * 60 * 24, "w": 60 * 60 * 24 * 7}


def convert_time(argument: str) -> Union[str, int]:
    """
    Convert time string into integer representing epoch seconds.
    """
    matches = re.findall(time_regex, argument.lower())
    time = 0
    for v, k in matches:
        # Here, we take k as " hour", " hrs", "min", " second", or anything
        # We standardize it by stripping space, and taking the first letter to determine smhd
        k = k.strip()[0]
        if k not in time_dict:
            return f"{k} is an invalid time-key! s/sec/m/min/h/hour/d/day are valid!"
        try:
            time += time_dict[k] * float(v)
        except ValueError:
            return f"{v} is not a number!"

    return int(time)
