def common_element(list1, list2):
     result = False
     for x in list1:
         for y in list2:
             if x == y:
                 result = True
                 return result


assert sum_list([10,20,30],[15,25,35])==[25,45,65]
assert sum_list([1,2,3],[5,6,7])==[6,8,10]
assert sum_list([15,20,30],[15,45,75])==[30,65,105]