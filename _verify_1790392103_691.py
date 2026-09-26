def Find_Max(arr):
    i = 0
    sum = 0
    for i in range(0, len(arr), 2):
        if arr[i] % 2 == 0:
            sum += arr[i]
    return sum


assert Find_Max([['A'],['A','B'],['A','B','C']]) == ['A','B','C']
assert Find_Max([[1],[1,2],[1,2,3]]) == [1,2,3]
assert Find_Max([[1,1],[1,2,3],[1,5,6,1]]) == [1,5,6,1]