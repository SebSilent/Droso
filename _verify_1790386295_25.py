def next_square_cube(*a):
    return [x * x * x for x in a[0]]



assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841