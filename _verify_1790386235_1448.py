def return_sum(*a):
    t = 0
    for x in a[0]:
        t += abs(x)
    return t



assert return_sum({'a': 100, 'b':200, 'c':300}) == 600
assert return_sum({'a': 25, 'b':18, 'c':45}) == 88
assert return_sum({'a': 36, 'b':39, 'c':49}) == 124