def cube_Sum(n):
    S = n * (n + 1) // 2
    res = S * (S - 1)
    return res


assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800