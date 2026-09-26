def is_product_even(data_list):
    total = 0
    for element in data_list:
        if type(element) == type([]):
            total = total + is_product_even(element)
        else:
            total = total + element
    return total


assert is_product_even([1,2,3])
assert is_product_even([1,2,1,4])
assert not is_product_even([1,1])