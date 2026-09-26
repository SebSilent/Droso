from math import tan, pi
from math import tan, pi
def area_polygon(s, l):
  area = s * (l ** 2) / (4 * tan(pi / s))
  return area
def prime_num(num):
  if num >=1:
   for i in range(2, num//2):
     if (num % i) == 0:
                return False
     else:
                return True
  else:
          return False
def wind_chill(*a):
    return prime_num(area_polygon(*a))



assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6