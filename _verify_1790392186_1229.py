import math

def toggle_middle_bits(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert toggle_middle_bits(9) == 15
assert toggle_middle_bits(10) == 12
assert toggle_middle_bits(11) == 13
assert toggle_middle_bits(0b1000001) == 0b1111111
assert toggle_middle_bits(0b1001101) == 0b1110011