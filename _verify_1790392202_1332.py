def is_polite(*a):
    return min(a[0])



assert is_polite(7) == 11
assert is_polite(4) == 7
assert is_polite(9) == 13