def add_tuple(test_list, test_tup):
  test_list += test_tup
  return test_list
def pos_count(list):
  pos_count= 0
  for num in list: 
    if num >= 0: 
      pos_count += 1
  return pos_count 
def frequency(*a):
    return pos_count(add_tuple(*a))



assert frequency([1,2,3], 4) == 0
assert frequency([1,2,2,3,3,3,4], 3) == 3
assert frequency([0,1,2,3,1,2], 1) == 2