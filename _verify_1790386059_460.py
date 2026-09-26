def count_Primes_nums(*a):
    return [x for x in a[0] if x % 2 == 1]



assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25