def count_divisors(*a):
    return [x for x in a[0] if x % 2 == 1]



assert count_divisors(10)
assert not count_divisors(100)
assert count_divisors(125)