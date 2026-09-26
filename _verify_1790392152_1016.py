def get_ludic(nums):
    get_ludic = list(filter(lambda nums: nums < 0, nums))
    return sum(get_ludic)


assert get_ludic(10) == [1, 2, 3, 5, 7]
assert get_ludic(25) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25]
assert get_ludic(45) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25, 29, 37, 41, 43]