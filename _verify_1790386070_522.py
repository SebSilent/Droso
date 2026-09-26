def div_list(nums1,nums2):
  result = map(lambda x, y: x / y, nums1, nums2)
  return list(result)
def Diff(li1,li2):
    return list(set(li1)-set(li2)) + list(set(li2)-set(li1))
 
def sub_list(*a):
    return Diff(div_list(*a), *a[1:])



assert sub_list([1, 2, 3],[4,5,6])==[-3,-3,-3]
assert sub_list([1,2],[3,4])==[-2,-2]
assert sub_list([90,120],[50,70])==[40,50]