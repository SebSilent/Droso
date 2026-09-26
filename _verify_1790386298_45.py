def next_square_cube(*a):
    return [x for x in a[0] if x % 2 == 1]



assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841