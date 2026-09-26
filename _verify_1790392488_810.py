def nth_nums(nums,n):
 nth_nums = list(map(lambda x: x ** n, nums))
 return nth_nums
def hexagonal_num(n): 
	return n*(2*n - 1) 
def angle_complex(*a):
    return hexagonal_num(nth_nums(*a))



import math
assert math.isclose(angle_complex(0,1j), 1.5707963267948966, rel_tol=0.001)
assert math.isclose(angle_complex(2,1j), 0.4636476090008061, rel_tol=0.001)
assert math.isclose(angle_complex(0,2j), 1.5707963267948966, rel_tol=0.001)