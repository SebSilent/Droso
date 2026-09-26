def next_Perfect_Square(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert next_Perfect_Square(35) == 36
assert next_Perfect_Square(6) == 9
assert next_Perfect_Square(9) == 16