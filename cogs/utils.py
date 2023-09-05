import re
from discord.ext import commands

time_regex = re.compile("(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"s": 1, "m": 60, "h": 60 * 60, "d": 60 * 60 * 60}


def convert_time(argument):
    """
    Convert time string for mute commands into integer representing seconds.
    """
    matches = re.findall(time_regex, argument.lower())
    time = 0
    for v, k in matches:
        # Here, we take k as " hour", " hrs", "min", " second", or anything
        # We standardize it by stripping space, and taking the first letter to determine smhd
        k = k.strip()[0]
        if k not in time_dict:
            raise commands.BadArgument("{} is an invalid time-key! s/m/h/d are valid!".format(k))
        try:
            time += time_dict[k] * float(v)
        except ValueError:
            raise commands.BadArgument("{} is not a number!".format(v))

    return time
