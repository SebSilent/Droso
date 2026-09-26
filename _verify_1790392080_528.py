def Diff(li1,li2):
    return list(set(li1)-set(li2)) + list(set(li2)-set(li1))
 


assert sub_list([1, 2, 3],[4,5,6])==[-3,-3,-3]
assert sub_list([1,2],[3,4])==[-2,-2]
assert sub_list([90,120],[50,70])==[40,50]