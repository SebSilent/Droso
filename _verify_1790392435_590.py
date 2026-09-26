def count_char_position(str1):
    total = 0
    for i in str1:
        total = total + 1
    return total


assert count_char_position("xbcefg") == 2
assert count_char_position("ABcED") == 3
assert count_char_position("AbgdeF") == 5