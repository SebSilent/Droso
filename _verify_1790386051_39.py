def are_equivalent(dict, n):
    result = all((x == n for x in dict.values()))
    return result


assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True