def cube_Sum(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800