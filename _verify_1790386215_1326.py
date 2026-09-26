def is_polite(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert is_polite(7) == 11
assert is_polite(4) == 7
assert is_polite(9) == 13