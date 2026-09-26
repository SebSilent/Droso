def is_nonagonal(n):
    return 6 * n * (n - 1) + 1


assert is_nonagonal(10) == 325
assert is_nonagonal(15) == 750
assert is_nonagonal(18) == 1089