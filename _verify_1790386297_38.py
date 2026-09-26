def next_square_cube(*a):
    t = 0
    for x in a[0]:
        t += x * x
    return t



assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841