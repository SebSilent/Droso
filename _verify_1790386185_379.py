def neg_nos(list1):
  out = []
  for num in list1: 
    if num < 0: 
      out.append(num)
  return out 


assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False