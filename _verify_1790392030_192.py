def nth_nums(nums,n):
 nth_nums = list(map(lambda x: x ** n, nums))
 return nth_nums
def is_octagonal(n): 
	return 3 * n * n - 2 * n 
def angle_complex(*a):
    return is_octagonal(nth_nums(*a))



import math
assert math.isclose(angle_complex(0,1j), 1.5707963267948966, rel_tol=0.001)
assert math.isclose(angle_complex(2,1j), 0.4636476090008061, rel_tol=0.001)
assert math.isclose(angle_complex(0,2j), 1.5707963267948966, rel_tol=0.001)