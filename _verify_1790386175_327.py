def count_Primes_nums(*a):
    return [x * x for x in a[0]]



assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25