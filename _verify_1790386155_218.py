def intersection_array(array_nums1,array_nums2):
 result = list(filter(lambda x: x in array_nums1, array_nums2)) 
 return result


assert surfacearea_cylinder(10,5)==942.45
assert surfacearea_cylinder(4,5)==226.18800000000002
assert surfacearea_cylinder(4,10)==351.848