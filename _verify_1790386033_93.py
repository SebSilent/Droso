def triangle_area(*a):

    r = a[0]
    if r < 0:
        return None
    return r * r



assert triangle_area(-1) == None
assert triangle_area(0) == 0
assert triangle_area(2) == 4