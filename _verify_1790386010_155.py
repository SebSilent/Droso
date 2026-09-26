def intersection_array(array_nums1,array_nums2):
 result = list(filter(lambda x: x in array_nums1, array_nums2)) 
 return result
def hexagonal_num(n): 
	return n*(2*n - 1) 
def eulerian_num(*a):
    return hexagonal_num(intersection_array(*a))



assert eulerian_num(3, 1) == 4
assert eulerian_num(4, 1) == 11
assert eulerian_num(5, 3) == 26