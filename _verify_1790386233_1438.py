def return_sum(d):
    if isinstance(d, dict):
        return 1 + (max(map(dict_depth, d.values())) if d else 0)
    return 0


assert return_sum({'a': 100, 'b':200, 'c':300}) == 600
assert return_sum({'a': 25, 'b':18, 'c':45}) == 88
assert return_sum({'a': 36, 'b':39, 'c':49}) == 124