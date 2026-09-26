def is_product_even(*a):
    return [x for x in a[0] if x]



assert is_product_even([1,2,3])
assert is_product_even([1,2,1,4])
assert not is_product_even([1,1])