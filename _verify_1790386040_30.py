def count_Substrings(*a):
    t = 0
    for x in a[0]:
        t += len(x)
    return t



assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12