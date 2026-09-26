def max_Abs_Diff(test_list):
    temp = [abs(b - a) for a, b in test_list]
    res = max(temp)
    return res


assert max_Abs_Diff((2,1,5,3)) == 4
assert max_Abs_Diff((9,3,2,5,1)) == 8
assert max_Abs_Diff((3,2,1)) == 2