def add_tuple(test_list, test_tup):
  test_list += test_tup
  return test_list
def max_sum_list(lists):
 return max(lists, key=sum)
def max_of_nth(*a):
    return max_sum_list(add_tuple(*a))



assert max_of_nth([[5, 6, 7], [1, 3, 5], [8, 9, 19]], 2) == 19
assert max_of_nth([[6, 7, 8], [2, 4, 6], [9, 10, 20]], 1) == 10
assert max_of_nth([[7, 8, 9], [3, 5, 7], [10, 11, 21]], 1) == 11