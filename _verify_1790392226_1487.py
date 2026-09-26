def is_product_even(list1):
    is_product_even = all((not d for d in list1))
    return is_product_even


assert is_product_even([1,2,3])
assert is_product_even([1,2,1,4])
assert not is_product_even([1,1])