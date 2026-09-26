def count_samepair(list1,list2,list3):
    result = sum(m == n == o for m, n, o in zip(list1,list2,list3))
    return result
def count_list(input_list): 
    return len(input_list)
def test_three_equal(*a):
    return count_list(count_samepair(*a))



assert test_three_equal(1,1,1) == 3
assert test_three_equal(-1,-2,-3) == 0
assert test_three_equal(1,2,2) == 2