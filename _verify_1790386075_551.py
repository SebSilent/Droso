import math

def get_Inv_Count(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert get_Inv_Count([1,20,6,4,5]) == 5
assert get_Inv_Count([1,2,1]) == 1
assert get_Inv_Count([1,2,5,6,1]) == 3