def toggle_middle_bits(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert toggle_middle_bits(9) == 15
assert toggle_middle_bits(10) == 12
assert toggle_middle_bits(11) == 13
assert toggle_middle_bits(0b1000001) == 0b1111111
assert toggle_middle_bits(0b1001101) == 0b1110011