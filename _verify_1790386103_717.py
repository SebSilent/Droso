def extract_rear(test_tup):
    delim = "-"
    res = ''.join([str(ele) + delim for ele in test_tup])
    res = res[ : len(res) - len(delim)]
    return (str(res)) 


assert extract_rear(('Mers', 'for', 'Vers') ) == ['s', 'r', 's']
assert extract_rear(('Avenge', 'for', 'People') ) == ['e', 'r', 'e']
assert extract_rear(('Gotta', 'get', 'go') ) == ['a', 't', 'o']