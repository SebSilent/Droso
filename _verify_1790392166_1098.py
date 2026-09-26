def triangle_area(*a):
    return [x for x in a[0] if x % 2 == 1]



assert triangle_area(-1) == None
assert triangle_area(0) == 0
assert triangle_area(2) == 4