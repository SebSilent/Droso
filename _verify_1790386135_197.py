import math

def count_Primes_nums(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25