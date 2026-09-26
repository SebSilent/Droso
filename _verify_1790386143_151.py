def surfacearea_sphere(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



import math
assert math.isclose(surfacearea_sphere(10), 1256.6370614359173, rel_tol=0.001)
assert math.isclose(surfacearea_sphere(15), 2827.4333882308138, rel_tol=0.001)
assert math.isclose(surfacearea_sphere(20), 5026.548245743669, rel_tol=0.001)