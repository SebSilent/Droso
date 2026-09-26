def remove_nested(test_tup):
  res = tuple()
  for count, ele in enumerate(test_tup):
    if not isinstance(ele, tuple):
      res = res + (ele, )
  return (res) 


assert two_unique_nums([1,2,3,2,3,4,5]) == [1, 4, 5]
assert two_unique_nums([1,2,3,2,4,5]) == [1, 3, 4, 5]
assert two_unique_nums([1,2,3,4,5]) == [1, 2, 3, 4, 5]