def sum_negativenum(nums):
  sum_negativenum = list(filter(lambda nums:nums<0,nums))
  return sum(sum_negativenum)


assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6