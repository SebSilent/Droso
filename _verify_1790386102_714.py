def string_to_tuple(str1):
    result = tuple(x for x in str1 if not x.isspace()) 
    return result
def concatenate_tuple(test_tup):
    delim = "-"
    res = ''.join([str(ele) + delim for ele in test_tup])
    res = res[ : len(res) - len(delim)]
    return (str(res)) 
def extract_rear(*a):
    return concatenate_tuple(string_to_tuple(*a))



assert extract_rear(('Mers', 'for', 'Vers') ) == ['s', 'r', 's']
assert extract_rear(('Avenge', 'for', 'People') ) == ['e', 'r', 'e']
assert extract_rear(('Gotta', 'get', 'go') ) == ['a', 't', 'o']