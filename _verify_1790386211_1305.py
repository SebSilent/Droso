def unique_Element(nums):
    return all((nums[i] % 2 == i % 2 for i in range(len(nums))))


assert unique_Element([1,1,1]) == True
assert unique_Element([1,2,1,2]) == False
assert unique_Element([1,2,3,4,5]) == False