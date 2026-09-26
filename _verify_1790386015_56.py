def cube_Sum(*a):
    a = a[0]
    n = a[0]
    return 2 * n ** 2 * (n + 1) ** 2



assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800