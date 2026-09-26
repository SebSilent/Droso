def count_Primes_nums(n):
    return int(n * (4 * n * n - 1) / 3)


assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25