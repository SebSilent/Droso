import math

def triangle_area(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert triangle_area(-1) == None
assert triangle_area(0) == 0
assert triangle_area(2) == 4