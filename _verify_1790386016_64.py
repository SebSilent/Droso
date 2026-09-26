import math

def surfacearea_sphere(*a):
    return 4 * math.pi * a[0] ** 2



assert surfacearea_cylinder(10,5)==942.45
assert surfacearea_cylinder(4,5)==226.18800000000002
assert surfacearea_cylinder(4,10)==351.848