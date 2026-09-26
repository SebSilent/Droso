def count_Primes_nums(n):
    res = 0
    for i in range(n, 0, -1):
        if i & i - 1 == 0:
            res = i
            break
    return res


assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25