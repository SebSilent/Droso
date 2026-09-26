def add_tuple(test_list, test_tup):
  test_list += test_tup
  return test_list
def count_occurance(s):
  count = 0
  for i in range(len(s) - 2):
    if (s[i] == 's' and s[i+1] == 't' and s[i+2] == 'd'):
      count = count + 1
  return count
def frequency(*a):
    return count_occurance(add_tuple(*a))



assert frequency([1,2,3], 4) == 0
assert frequency([1,2,2,3,3,3,4], 3) == 3
assert frequency([0,1,2,3,1,2], 1) == 2