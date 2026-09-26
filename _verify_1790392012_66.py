def count_Substrings(str):
    str_len = len(str)
    return int(str_len * (str_len + 1) / 2)


assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12