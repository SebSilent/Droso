def circle_circumference(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



import math
assert math.isclose(circle_circumference(10), 62.830000000000005, rel_tol=0.001)
assert math.isclose(circle_circumference(5), 31.415000000000003, rel_tol=0.001)
assert math.isclose(circle_circumference(4), 25.132, rel_tol=0.001)