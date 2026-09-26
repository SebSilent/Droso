from math import tan, pi
import sys
from math import tan, pi
def area_polygon(s, l):
  area = s * (l ** 2) / (4 * tan(pi / s))
  return area
import sys
def next_smallest_palindrome(num):
    numstr = str(num)
    for i in range(num+1,sys.maxsize):
        if str(i) == str(i)[::-1]:
            return i
def wind_chill(*a):
    return next_smallest_palindrome(area_polygon(*a))



assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6