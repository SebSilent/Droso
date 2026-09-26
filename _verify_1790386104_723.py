def extract_rear(*a):
    out = []
    for x in a[0]:
        if x == a[1]:
            out.append(x)
    return out



assert extract_rear(('Mers', 'for', 'Vers') ) == ['s', 'r', 's']
assert extract_rear(('Avenge', 'for', 'People') ) == ['e', 'r', 'e']
assert extract_rear(('Gotta', 'get', 'go') ) == ['a', 't', 'o']