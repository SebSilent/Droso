def smallest_num(nums):
    smallest_num = next((el for el in nums if el % 2 != 0), -1)
    return smallest_num


assert smallest_num([10, 20, 1, 45, 99]) == 1
assert smallest_num([1, 2, 3]) == 1
assert smallest_num([45, 46, 50, 60]) == 45