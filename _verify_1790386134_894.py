def two_unique_nums(*a):
    out = []
    for x in a[0]:
        if x not in out:
            out.append(x)
    return out



assert two_unique_nums([1,2,3,2,3,4,5]) == [1, 4, 5]
assert two_unique_nums([1,2,3,2,4,5]) == [1, 3, 4, 5]
assert two_unique_nums([1,2,3,4,5]) == [1, 2, 3, 4, 5]