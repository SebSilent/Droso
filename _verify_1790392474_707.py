def pos_count(list):
  pos_count= 0
  for num in list: 
    if num >= 0: 
      pos_count += 1
  return pos_count 


assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12