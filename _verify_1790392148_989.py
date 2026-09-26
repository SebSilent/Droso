import math

def armstrong_number(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert armstrong_number(153)==True
assert armstrong_number(259)==False
assert armstrong_number(4458)==False