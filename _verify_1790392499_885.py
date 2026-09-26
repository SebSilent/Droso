def count_char_position(*a):
    return sum(1 for x in a[0] if x % 2 == 1)



assert count_char_position("xbcefg") == 2
assert count_char_position("ABcED") == 3
assert count_char_position("AbgdeF") == 5