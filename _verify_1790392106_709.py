def cube_Sum(*a):
    out = []
    for x in a[0]:
        out.append(x ** 3)
    return out



assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800