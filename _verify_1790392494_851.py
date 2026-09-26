def max_Abs_Diff(string):
    n = len(string)
    current_sum = 0
    max_sum = 0
    for i in range(n):
        current_sum += 1 if string[i] == '0' else -1
        if current_sum < 0:
            current_sum = 0
        max_sum = max(current_sum, max_sum)
    return max_sum if max_sum else 0


assert max_Abs_Diff((2,1,5,3)) == 4
assert max_Abs_Diff((9,3,2,5,1)) == 8
assert max_Abs_Diff((3,2,1)) == 2