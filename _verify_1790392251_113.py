import math
import math
def volume_sphere(r):
  volume=(4/3)*math.pi*r*r*r
  return volume
def lateralsuface_cylinder(r,h):
  lateralsurface= 2*3.1415*r*h
  return lateralsurface
def surfacearea_sphere(*a):
    return lateralsuface_cylinder(volume_sphere(*a), *a[1:])



import math
assert math.isclose(surfacearea_sphere(10), 1256.6370614359173, rel_tol=0.001)
assert math.isclose(surfacearea_sphere(15), 2827.4333882308138, rel_tol=0.001)
assert math.isclose(surfacearea_sphere(20), 5026.548245743669, rel_tol=0.001)