def count_Substrings(*a):
    return sorted(a[0], reverse=True)



assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12