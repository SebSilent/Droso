def triangle_area(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert triangle_area(-1) == None
assert triangle_area(0) == 0
assert triangle_area(2) == 4