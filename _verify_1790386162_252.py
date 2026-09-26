def count_Substrings(*a):
    return [x for x in a[0] if x % 2 == 1]



assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12