def cube_Sum(n):
    j = 0
    sm = 0
    for i in range(1, n + 1):
        j = 2 * i - 1
        sm = sm + j * j * j * j
    return sm


assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800