def are_equivalent(*a):
    t = 0
    for x in a[0]:
        t += x
    return t



assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True