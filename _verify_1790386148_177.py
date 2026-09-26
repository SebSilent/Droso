def dict_depth(d):
    if isinstance(d, dict):
        return 1 + (max(map(dict_depth, d.values())) if d else 0)
    return 0


import math
assert math.isclose(circle_circumference(10), 62.830000000000005, rel_tol=0.001)
assert math.isclose(circle_circumference(5), 31.415000000000003, rel_tol=0.001)
assert math.isclose(circle_circumference(4), 25.132, rel_tol=0.001)