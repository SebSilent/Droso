import math

def return_sum(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert return_sum({'a': 100, 'b':200, 'c':300}) == 600
assert return_sum({'a': 25, 'b':18, 'c':45}) == 88
assert return_sum({'a': 36, 'b':39, 'c':49}) == 124