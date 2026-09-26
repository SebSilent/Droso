def extract_freq(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert extract_freq([(3, 4), (1, 2), (4, 3), (5, 6)] ) == 3
assert extract_freq([(4, 15), (2, 3), (5, 4), (6, 7)] ) == 4
assert extract_freq([(5, 16), (2, 3), (6, 5), (6, 9)] ) == 4