def first_odd(nums):
  first_odd = next((el for el in nums if el%2!=0),-1)
  return first_odd


assert perfect_squares(1,30)==[1, 4, 9, 16, 25]
assert perfect_squares(50,100)==[64, 81, 100]
assert perfect_squares(100,200)==[100, 121, 144, 169, 196]