import math

def find_Parity(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert find_Parity(12) == False
assert find_Parity(7) == True
assert find_Parity(10) == False