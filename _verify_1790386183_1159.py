def is_nonagonal(n):
    return n * (n + 1) * (n + 2) / 6


assert is_nonagonal(10) == 325
assert is_nonagonal(15) == 750
assert is_nonagonal(18) == 1089