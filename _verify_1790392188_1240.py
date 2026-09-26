def divisible_by_digits(startnum, endnum):
    return [n for n in range(startnum, endnum+1) \
                if not any(map(lambda x: int(x) == 0 or n%int(x) != 0, str(n)))]


assert geometric_sum(7) == 1.9921875
assert geometric_sum(4) == 1.9375
assert geometric_sum(8) == 1.99609375