def all_unique(test_list):
    if len(test_list) > len(set(test_list)):
        return False
    return True
def extract_nth_element(list1, n):
    result = [x[n] for x in list1]
    return result
def extract_freq(*a):
    return extract_nth_element(all_unique(*a), *a[1:])



assert extract_freq([(3, 4), (1, 2), (4, 3), (5, 6)] ) == 3
assert extract_freq([(4, 15), (2, 3), (5, 4), (6, 7)] ) == 4
assert extract_freq([(5, 16), (2, 3), (6, 5), (6, 9)] ) == 4