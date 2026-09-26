def is_product_even(l):
    return sorted(l) == list(range(min(l), max(l) + 1))


assert is_product_even([1,2,3])
assert is_product_even([1,2,1,4])
assert not is_product_even([1,1])