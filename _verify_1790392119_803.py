def Find_Min(arr):
    Sum = 0
    l = len(arr)
    for i in range(l):
        Sum += ((i + 1) * (l - i) + 1) // 2 * arr[i]
    return Sum


assert Find_Min([[1],[1,2],[1,2,3]]) == [1]
assert Find_Min([[1,1],[1,1,1],[1,2,7,8]]) == [1,1]
assert Find_Min([['x'],['x','y'],['x','y','z']]) == ['x']