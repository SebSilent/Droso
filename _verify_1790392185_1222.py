def toggle_middle_bits(*a):
    return sorted(a[0], reverse=True)



assert toggle_middle_bits(9) == 15
assert toggle_middle_bits(10) == 12
assert toggle_middle_bits(11) == 13
assert toggle_middle_bits(0b1000001) == 0b1111111
assert toggle_middle_bits(0b1001101) == 0b1110011