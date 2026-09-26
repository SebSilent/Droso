def find_Max_Num(arr) : 
    n = len(arr)
    arr.sort(reverse = True) 
    num = arr[0] 
    for i in range(1,n) : 
        num = num * 10 + arr[i] 
    return num 


assert triangle_area(-1) == None
assert triangle_area(0) == 0
assert triangle_area(2) == 4