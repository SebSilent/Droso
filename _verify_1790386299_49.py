def next_square_cube(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841