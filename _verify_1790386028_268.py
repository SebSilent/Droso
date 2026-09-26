def all_Characters_Same(s) :
    n = len(s)
    for i in range(1,n) :
        if s[i] != s[0] :
            return False
    return True


assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True