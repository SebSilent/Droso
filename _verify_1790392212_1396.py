def last(arr, n):
    mul = 1
    for i in range(len(arr)):
        mul = mul * (arr[i] % n) % n
    return mul % n


assert last([1,2,3],1) == 0
assert last([1,1,1,2,3,4],1) == 2
assert last([2,3,2,3,6,8,9],3) == 3