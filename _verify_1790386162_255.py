def count_Substrings(*a):
    return sum(1 for x in a[0] if True)



assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12