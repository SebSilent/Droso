def upper_ctr(str):
    upper_ctr = 0
    for i in range(len(str)):
          if str[i] >= 'A' and str[i] <= 'Z': upper_ctr += 1
          return upper_ctr


assert get_Char("abc") == "f"
assert get_Char("gfg") == "t"
assert get_Char("ab") == "c"