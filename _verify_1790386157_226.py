def triangle_area(*a):
    m = a[0][0]
    for x in a[0]:
        if x > m:
            m = x
    return m



assert triangle_area(-1) == None
assert triangle_area(0) == 0
assert triangle_area(2) == 4