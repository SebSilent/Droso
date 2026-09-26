def return_sum(dict1):
    dict1 = {key: value for key, value in dict1.items() if value is not None}
    return dict1


assert return_sum({'a': 100, 'b':200, 'c':300}) == 600
assert return_sum({'a': 25, 'b':18, 'c':45}) == 88
assert return_sum({'a': 36, 'b':39, 'c':49}) == 124