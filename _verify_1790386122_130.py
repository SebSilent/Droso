def are_equivalent(x, y):
    if y < 0:
        return -are_equivalent(x, -y)
    elif y == 0:
        return 0
    elif y == 1:
        return x
    else:
        return x + are_equivalent(x, y - 1)


assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True