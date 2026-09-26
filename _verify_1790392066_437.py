def babylonian_squareroot(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



import math
assert math.isclose(babylonian_squareroot(10), 3.162277660168379, rel_tol=0.001)
assert math.isclose(babylonian_squareroot(2), 1.414213562373095, rel_tol=0.001)
assert math.isclose(babylonian_squareroot(9), 3.0, rel_tol=0.001)