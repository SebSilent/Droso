def find_sum(nums):
    find_sum = next((el for el in nums if el % 2 != 0), -1)
    return find_sum


assert find_sum([1,2,3,1,1,4,5,6]) == 21
assert find_sum([1,10,9,4,2,10,10,45,4]) == 71
assert find_sum([12,10,9,45,2,10,10,45,10]) == 78