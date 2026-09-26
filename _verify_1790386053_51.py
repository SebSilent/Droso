def are_equivalent(*a):
    return a[0] / a[1]



assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True