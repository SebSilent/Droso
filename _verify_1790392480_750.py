def power(*a):
    return a[0] ** a[1] if isinstance(a[1], int) and abs(a[1]) <= 64 else None



assert power(3,4) == 81
assert power(2,3) == 8
assert power(5,5) == 3125