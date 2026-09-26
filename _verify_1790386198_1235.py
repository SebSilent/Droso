import bisect
def left_insertion(a, x):
    i = bisect.bisect_left(a, x)
    return i


assert geometric_sum(7) == 1.9921875
assert geometric_sum(4) == 1.9375
assert geometric_sum(8) == 1.99609375