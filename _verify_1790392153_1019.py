def move_num(test_str):
  res = ''
  dig = ''
  for ele in test_str:
    if ele.isdigit():
      dig += ele
    else:
      res += ele
  res += dig
  return (res) 


assert get_ludic(10) == [1, 2, 3, 5, 7]
assert get_ludic(25) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25]
assert get_ludic(45) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25, 29, 37, 41, 43]