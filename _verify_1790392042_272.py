def count_char_position(str):
    count_char_position = 0
    for i in range(len(str)):
        if str[i] >= 'A' and str[i] <= 'Z':
            count_char_position += 1
        return count_char_position


assert count_char_position("xbcefg") == 2
assert count_char_position("ABcED") == 3
assert count_char_position("AbgdeF") == 5