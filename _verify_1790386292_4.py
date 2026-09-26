def next_square_cube(n):
    j = 0
    sm = 0
    for i in range(1, n + 1):
        j = 2 * i - 1
        sm = sm + j * j * j * j
    return sm


assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841