def is_polite(n):
    return 6 * n * (n - 1) + 1


assert is_polite(7) == 11
assert is_polite(4) == 7
assert is_polite(9) == 13