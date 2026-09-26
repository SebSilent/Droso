def tuple_modulo(test_tup1, test_tup2):
  res = tuple(ele1 % ele2 for ele1, ele2 in zip(test_tup1, test_tup2)) 
  return (res) 


assert sub_list([1, 2, 3],[4,5,6])==[-3,-3,-3]
assert sub_list([1,2],[3,4])==[-2,-2]
assert sub_list([90,120],[50,70])==[40,50]