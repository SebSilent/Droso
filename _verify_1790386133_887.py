def two_unique_nums(nums):
    two_unique_nums = next((el for el in nums if el % 2 != 0), -1)
    return two_unique_nums


assert two_unique_nums([1,2,3,2,3,4,5]) == [1, 4, 5]
assert two_unique_nums([1,2,3,2,4,5]) == [1, 3, 4, 5]
assert two_unique_nums([1,2,3,4,5]) == [1, 2, 3, 4, 5]