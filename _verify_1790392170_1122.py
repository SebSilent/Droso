from math import tan, pi
from math import tan, pi
def area_polygon(s, l):
  area = s * (l ** 2) / (4 * tan(pi / s))
  return area
def sum_negativenum(nums):
  sum_negativenum = list(filter(lambda nums:nums<0,nums))
  return sum(sum_negativenum)
def wind_chill(*a):
    return sum_negativenum(area_polygon(*a))



assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6