def count_Primes_nums(nums):
    count_Primes_nums = next((el for el in nums if el % 2 != 0), -1)
    return count_Primes_nums


assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25