def upper_ctr(str):
    upper_ctr = 0
    for i in range(len(str)):
          if str[i] >= 'A' and str[i] <= 'Z': upper_ctr += 1
          return upper_ctr


assert count_char_position("xbcefg") == 2
assert count_char_position("ABcED") == 3
assert count_char_position("AbgdeF") == 5