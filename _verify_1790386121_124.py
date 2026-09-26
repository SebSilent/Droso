def number_ctr(str):
      number_ctr= 0
      for i in range(len(str)):
          if str[i] >= '0' and str[i] <= '9': number_ctr += 1     
      return  number_ctr


assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12