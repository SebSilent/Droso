def count_Primes_nums(list1):
    ctr = 0
    for i in list1:
        if isinstance(i, int):
            ctr = ctr + 1
    return ctr


assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25