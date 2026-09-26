import math

def issort_list(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert issort_list([1,2,4,6,8,10,12,14,16,17])==True
assert issort_list([1, 2, 4, 6, 8, 10, 12, 14, 20, 17])==False
assert issort_list([1, 2, 4, 6, 8, 10,15,14,20])==False