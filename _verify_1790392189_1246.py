def geometric_sum(*a):
    t = 0
    for x in a[0]:
        t += abs(x)
    return t



assert geometric_sum(7) == 1.9921875
assert geometric_sum(4) == 1.9375
assert geometric_sum(8) == 1.99609375