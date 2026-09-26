def add_tuple(test_list, test_tup):
  test_list += test_tup
  return test_list
def count_list(input_list): 
    return len(input_list)
def frequency(*a):
    return count_list(add_tuple(*a))



assert frequency([1,2,3], 4) == 0
assert frequency([1,2,2,3,3,3,4], 3) == 3
assert frequency([0,1,2,3,1,2], 1) == 2