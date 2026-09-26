def tuple_modulo(test_tup1, test_tup2):
  res = tuple(ele1 % ele2 for ele1, ele2 in zip(test_tup1, test_tup2)) 
  return (res) 


assert division_elements((10, 4, 6, 9),(5, 2, 3, 3)) == (2, 2, 2, 3)
assert division_elements((12, 6, 8, 16),(6, 3, 4, 4)) == (2, 2, 2, 4)
assert division_elements((20, 14, 36, 18),(5, 7, 6, 9)) == (4, 2, 6, 2)