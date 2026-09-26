def last(arr):  
    sum=0
    for i in arr: 
        sum = sum + i      
    return(sum)  


assert last([1,2,3],1) == 0
assert last([1,1,1,2,3,4],1) == 2
assert last([2,3,2,3,6,8,9],3) == 3