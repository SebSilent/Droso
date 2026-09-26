def count_samepair(list1,list2,list3):
    result = sum(m == n == o for m, n, o in zip(list1,list2,list3))
    return result
def number_ctr(str):
      number_ctr= 0
      for i in range(len(str)):
          if str[i] >= '0' and str[i] <= '9': number_ctr += 1     
      return  number_ctr
def test_three_equal(*a):
    return number_ctr(count_samepair(*a))



assert test_three_equal(1,1,1) == 3
assert test_three_equal(-1,-2,-3) == 0
assert test_three_equal(1,2,2) == 2