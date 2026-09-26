def count_char_position(s):
    count = 0
    for i in range(len(s) - 2):
        if s[i] == 's' and s[i + 1] == 't' and (s[i + 2] == 'd'):
            count = count + 1
    return count


assert count_char_position("xbcefg") == 2
assert count_char_position("ABcED") == 3
assert count_char_position("AbgdeF") == 5