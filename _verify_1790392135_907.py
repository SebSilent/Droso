def lateralsuface_cylinder(r,h):
  lateralsurface= 2*3.1415*r*h
  return lateralsurface
def rectangle_area(l,b):
  area=l*b
  return area
def surfacearea_cylinder(*a):
    return rectangle_area(lateralsuface_cylinder(*a), *a[1:])



assert surfacearea_cylinder(10,5)==942.45
assert surfacearea_cylinder(4,5)==226.18800000000002
assert surfacearea_cylinder(4,10)==351.848