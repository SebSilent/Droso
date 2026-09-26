def max_sum(arr):
    n = len(arr)
    max_ending_here = 1
    min_ending_here = 1
    max_so_far = 0
    flag = 0
    for i in range(0, n):
        if arr[i] > 0:
            max_ending_here = max_ending_here * arr[i]
            min_ending_here = min(min_ending_here * arr[i], 1)
            flag = 1
        elif arr[i] == 0:
            max_ending_here = 1
            min_ending_here = 1
        else:
            temp = max_ending_here
            max_ending_here = max(min_ending_here * arr[i], 1)
            min_ending_here = temp * arr[i]
        if max_so_far < max_ending_here:
            max_so_far = max_ending_here
    if flag == 0 and max_so_far == 0:
        return 0
    return max_so_far


assert max_sum([1, 15, 51, 45, 33, 100, 12, 18, 9]) == 194
assert max_sum([80, 60, 30, 40, 20, 10]) == 210
assert max_sum([2, 3 ,14, 16, 21, 23, 29, 30]) == 138