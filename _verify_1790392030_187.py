def and_tuples(test_tup1, test_tup2):
  res = tuple(ele1 & ele2 for ele1, ele2 in zip(test_tup1, test_tup2))
  return (res) 


assert add_lists([5, 6, 7], (9, 10)) == (9, 10, 5, 6, 7)
assert add_lists([6, 7, 8], (10, 11)) == (10, 11, 6, 7, 8)
assert add_lists([7, 8, 9], (11, 12)) == (11, 12, 7, 8, 9)