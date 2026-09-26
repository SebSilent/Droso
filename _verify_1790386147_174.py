def intersection_array(array_nums1,array_nums2):
 result = list(filter(lambda x: x in array_nums1, array_nums2)) 
 return result


import math
assert math.isclose(circle_circumference(10), 62.830000000000005, rel_tol=0.001)
assert math.isclose(circle_circumference(5), 31.415000000000003, rel_tol=0.001)
assert math.isclose(circle_circumference(4), 25.132, rel_tol=0.001)