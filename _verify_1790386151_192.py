def cube_Sum(*a):
    return [x * x * x for x in a[0]]



assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800