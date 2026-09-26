def find_remainder(arr, n): 
    mul = 1
    for i in range(len(arr)):  
        mul = (mul * (arr[i] % n)) % n 
    return mul % n 
def search(arr):
    n = len(arr)
    XOR = 0
    for i in range(n) :
        XOR = XOR ^ arr[i]
    return (XOR)
def last(*a):
    return search(find_remainder(*a))



assert last([1,2,3],1) == 0
assert last([1,1,1,2,3,4],1) == 2
assert last([2,3,2,3,6,8,9],3) == 3