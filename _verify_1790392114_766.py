def add_tuple(test_list, test_tup):
  test_list += test_tup
  return test_list
def count(lst):   
    return sum(lst) 
def count_Occurrence(*a):
    return count(add_tuple(*a))



assert count_Occurrence(('a', 'a', 'c', 'b', 'd'),['a', 'b'] ) == 3
assert count_Occurrence((1, 2, 3, 1, 4, 6, 7, 1, 4),[1, 4, 7]) == 6
assert count_Occurrence((1,2,3,4,5,6),[1,2]) == 2