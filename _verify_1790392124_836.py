def new_tuple(test_list, test_str):
  return tuple(test_list + [test_str])


assert remove_lowercase("PYTHon")==('PYTH')
assert remove_lowercase("FInD")==('FID')
assert remove_lowercase("STRinG")==('STRG')