def get_ludic(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert get_ludic(10) == [1, 2, 3, 5, 7]
assert get_ludic(25) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25]
assert get_ludic(45) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25, 29, 37, 41, 43]