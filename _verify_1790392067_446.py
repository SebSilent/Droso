import math

def babylonian_squareroot(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



import math
assert math.isclose(babylonian_squareroot(10), 3.162277660168379, rel_tol=0.001)
assert math.isclose(babylonian_squareroot(2), 1.414213562373095, rel_tol=0.001)
assert math.isclose(babylonian_squareroot(9), 3.0, rel_tol=0.001)