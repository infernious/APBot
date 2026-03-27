import re
from typing import Union

time_regex = re.compile(r"(\d{1,5})([smhdw])")
time_dict = {"s": 1, "m": 60, "h": 60 * 60, "d": 60 * 60 * 24, "w": 60 * 60 * 24 * 7}


def convert_time(argument: str) -> Union[str, int]:
    """
    Convert time string into integer representing epoch seconds.
    """
    cleaned_argument = argument.lower().strip()
    invalid_key = next((char for char in cleaned_argument if char.isalpha() and char not in time_dict), None)
    if invalid_key:
        return f"{invalid_key} is an invalid time-key! s/sec/m/min/h/hour/d/day are valid!"

    matches = list(time_regex.finditer(cleaned_argument))
    if not matches:
        return f"{argument} is not a valid duration!"

    reconstructed = "".join(match.group(0) for match in matches)
    if reconstructed != cleaned_argument:
        return f"{argument} is not a valid duration!"

    time = 0
    for match in matches:
        v, k = match.groups()
        if k not in time_dict:
            return f"{k} is an invalid time-key! s/sec/m/min/h/hour/d/day are valid!"
        try:
            time += time_dict[k] * float(v)
        except ValueError:
            return f"{v} is not a number!"

    return int(time)
