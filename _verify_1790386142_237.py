def first_odd(nums):
  first_odd = next((el for el in nums if el%2!=0),-1)
  return first_odd


assert test_three_equal(1,1,1) == 3
assert test_three_equal(-1,-2,-3) == 0
assert test_three_equal(1,2,2) == 2