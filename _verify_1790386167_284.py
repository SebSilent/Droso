def sum_even_and_even_index(arr):  
    i = 0
    sum = 0
    for i in range(0, len(arr),2): 
        if (arr[i] % 2 == 0) : 
            sum += arr[i]  
    return sum


assert min_of_three(10,20,0)==0
assert min_of_three(19,15,18)==15
assert min_of_three(-10,-20,-30)==-30