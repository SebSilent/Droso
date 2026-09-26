import math

def is_not_prime(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False