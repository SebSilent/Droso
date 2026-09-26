import math
def median_numbers(a,b,c):
 if a > b:
    if a < c:
        median = a
    elif b > c:
        median = b
    else:
        median = c
 else:
    if a > c:
        median = a
    elif b < c:
        median = b
    else:
        median = c
 return median
import math
def volume_sphere(r):
  volume=(4/3)*math.pi*r*r*r
  return volume
def parabola_directrix(*a):
    return volume_sphere(median_numbers(*a))



assert parabola_directrix(5,3,2)==-198
assert parabola_directrix(9,8,4)==-2336
assert parabola_directrix(2,4,6)==-130