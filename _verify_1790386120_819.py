import math

def add_pairwise(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert add_pairwise((1, 5, 7, 8, 10)) == (6, 12, 15, 18)
assert add_pairwise((2, 6, 8, 9, 11)) == (8, 14, 17, 20)
assert add_pairwise((3, 7, 9, 10, 12)) == (10, 16, 19, 22)