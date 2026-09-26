def is_product_even(*a):
    out = []
    for x in a[0]:
        if x % 2 == 0:
            out.append(x)
    return out



assert is_product_even([1,2,3])
assert is_product_even([1,2,1,4])
assert not is_product_even([1,1])