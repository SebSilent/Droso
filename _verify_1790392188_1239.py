def geometric_sum(*a):
    return [x for x in a[0] if x % 2 == 1]



assert geometric_sum(7) == 1.9921875
assert geometric_sum(4) == 1.9375
assert geometric_sum(8) == 1.99609375