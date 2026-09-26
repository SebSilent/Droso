def get_pairs_count(arr, sum):
    count = 0  
    for i in range(len(arr)):
        for j in range(i + 1,len(arr)):
            if arr[i] + arr[j] == sum:
                count += 1
    return count


assert test_three_equal(1,1,1) == 3
assert test_three_equal(-1,-2,-3) == 0
assert test_three_equal(1,2,2) == 2