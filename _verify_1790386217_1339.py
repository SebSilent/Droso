import math

def is_polite(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert is_polite(7) == 11
assert is_polite(4) == 7
assert is_polite(9) == 13