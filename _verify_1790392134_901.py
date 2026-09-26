import math

def two_unique_nums(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert two_unique_nums([1,2,3,2,3,4,5]) == [1, 4, 5]
assert two_unique_nums([1,2,3,2,4,5]) == [1, 3, 4, 5]
assert two_unique_nums([1,2,3,4,5]) == [1, 2, 3, 4, 5]