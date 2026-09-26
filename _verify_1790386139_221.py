def count_samepair(list1,list2,list3):
    result = sum(m == n == o for m, n, o in zip(list1,list2,list3))
    return result
def pos_count(list):
  pos_count= 0
  for num in list: 
    if num >= 0: 
      pos_count += 1
  return pos_count 
def test_three_equal(*a):
    return pos_count(count_samepair(*a))



assert test_three_equal(1,1,1) == 3
assert test_three_equal(-1,-2,-3) == 0
assert test_three_equal(1,2,2) == 2