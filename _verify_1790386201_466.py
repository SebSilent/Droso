def count_Primes_nums(*a):
    out = []
    for x in a[0]:
        if x % 2 == 1:
            out.append(x)
    return out



assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25