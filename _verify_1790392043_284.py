def count_char_position(*a):
    return [x for x in a[0] if x % 2 == 1]



assert count_char_position("xbcefg") == 2
assert count_char_position("ABcED") == 3
assert count_char_position("AbgdeF") == 5