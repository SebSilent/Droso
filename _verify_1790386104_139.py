def test_three_equal(*a):
    return sum(1 for x in a[0] if x in a[1])



assert test_three_equal(1,1,1) == 3
assert test_three_equal(-1,-2,-3) == 0
assert test_three_equal(1,2,2) == 2