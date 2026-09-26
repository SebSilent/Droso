def frequency(*a):
    return sum(1 for x in a[0] if x == a[1])



assert frequency([1,2,3], 4) == 0
assert frequency([1,2,2,3,3,3,4], 3) == 3
assert frequency([0,1,2,3,1,2], 1) == 2