def geometric_sum(h_age):
    if h_age < 0:
        exit()
    elif h_age <= 2:
        d_age = h_age * 10.5
    else:
        d_age = 21 + (h_age - 2) * 4
    return d_age


assert geometric_sum(7) == 1.9921875
assert geometric_sum(4) == 1.9375
assert geometric_sum(8) == 1.99609375