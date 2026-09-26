def multiply_int(x, y):
    if y < 0:
        return -multiply_int(x, -y)
    elif y == 0:
        return 0
    elif y == 1:
        return x
    else:
        return x + multiply_int(x, y - 1)
def check_value(dict, n):
    result = all(x == n for x in dict.values()) 
    return result
def are_equivalent(*a):
    return check_value(multiply_int(*a), *a[1:])



assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True