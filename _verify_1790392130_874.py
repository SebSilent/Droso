def issort_list(list1):
 empty_dit=all(not d for d in list1)
 return empty_dit


assert issort_list([1,2,4,6,8,10,12,14,16,17])==True
assert issort_list([1, 2, 4, 6, 8, 10, 12, 14, 20, 17])==False
assert issort_list([1, 2, 4, 6, 8, 10,15,14,20])==False