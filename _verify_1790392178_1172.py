def is_nonagonal(*a):
    return [x * x for x in a[0]]



assert is_nonagonal(10) == 325
assert is_nonagonal(15) == 750
assert is_nonagonal(18) == 1089