def all_unique(test_list):
    if len(test_list) > len(set(test_list)):
        return False
    return True
def and_tuples(test_tup1, test_tup2):
  res = tuple(ele1 & ele2 for ele1, ele2 in zip(test_tup1, test_tup2))
  return (res) 
def extract_freq(*a):
    return and_tuples(all_unique(*a), *a[1:])



assert extract_freq([(3, 4), (1, 2), (4, 3), (5, 6)] ) == 3
assert extract_freq([(4, 15), (2, 3), (5, 4), (6, 7)] ) == 4
assert extract_freq([(5, 16), (2, 3), (6, 5), (6, 9)] ) == 4