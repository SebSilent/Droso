def dict_filter(dict,n):
 result = {key:value for (key, value) in dict.items() if value >=n}
 return result
def multiply_elements(test_tup):
  res = tuple(i * j for i, j in zip(test_tup, test_tup[1:]))
  return (res) 
def get_total_number_of_sequences(*a):
    return multiply_elements(dict_filter(*a))



assert get_total_number_of_sequences(10, 4) == 4
assert get_total_number_of_sequences(5, 2) == 6
assert get_total_number_of_sequences(16, 3) == 84