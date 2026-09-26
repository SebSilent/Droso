def intersection_array(array_nums1,array_nums2):
 result = list(filter(lambda x: x in array_nums1, array_nums2)) 
 return result
def tetrahedral_number(n): 
	return (n * (n + 1) * (n + 2)) / 6
def eulerian_num(*a):
    return tetrahedral_number(intersection_array(*a))



assert eulerian_num(3, 1) == 4
assert eulerian_num(4, 1) == 11
assert eulerian_num(5, 3) == 26