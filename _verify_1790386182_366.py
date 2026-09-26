def is_not_prime(nums):
    odd_nums = list(filter(lambda x: x % 2 != 0, nums))
    return odd_nums


assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False