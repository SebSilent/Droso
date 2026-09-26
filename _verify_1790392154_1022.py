import math

def get_ludic(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert get_ludic(10) == [1, 2, 3, 5, 7]
assert get_ludic(25) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25]
assert get_ludic(45) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25, 29, 37, 41, 43]