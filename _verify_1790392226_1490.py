import math

def is_product_even(*a):
    return math.prod(a[0])



assert is_product_even([1,2,3])
assert is_product_even([1,2,1,4])
assert not is_product_even([1,1])