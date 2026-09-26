def count_divisors(nums):
    return all((nums[i] % 2 == i % 2 for i in range(len(nums))))


assert count_divisors(10)
assert not count_divisors(100)
assert count_divisors(125)