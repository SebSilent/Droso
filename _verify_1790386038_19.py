def is_not_prime(*a):
    n = a[0]
    if n < 2:
        return True
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return True
    return False



assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False