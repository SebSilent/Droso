import math
def lateralsurface_cone(r,h):
  l = math.sqrt(r * r + h * h)
  LSA = math.pi * r  * l
  return LSA


assert surfacearea_cylinder(10,5)==942.45
assert surfacearea_cylinder(4,5)==226.18800000000002
assert surfacearea_cylinder(4,10)==351.848