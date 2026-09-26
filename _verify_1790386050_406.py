import math

def next_Perfect_Square(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert next_Perfect_Square(35) == 36
assert next_Perfect_Square(6) == 9
assert next_Perfect_Square(9) == 16