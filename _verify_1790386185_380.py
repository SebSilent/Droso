def is_not_prime(*a):
    return [x for x in a[0] if x]



assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False