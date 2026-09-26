def next_square_cube(n):
    S = n * (n + 1) // 2
    res = S * (S - 1)
    return res


assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841