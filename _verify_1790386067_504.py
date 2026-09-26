def count_X(tup, x): 
    count = 0
    for ele in tup: 
        if (ele == x): 
            count = count + 1
    return count 
def rear_extract(test_list):
  res = [lis[-1] for lis in test_list]
  return (res) 
def sequential_search(*a):
    return rear_extract(count_X(*a))



assert sequential_search([11,23,58,31,56,77,43,12,65,19],31) == (True, 3)
assert sequential_search([12, 32, 45, 62, 35, 47, 44, 61],61) == (True, 7)
assert sequential_search([9, 10, 17, 19, 22, 39, 48, 56],48) == (True, 6)