def geometric_sum(list_data):
    temp = list(set(list_data))
    p = 1
    for i in temp:
        p *= i
    return p


assert geometric_sum(7) == 1.9921875
assert geometric_sum(4) == 1.9375
assert geometric_sum(8) == 1.99609375