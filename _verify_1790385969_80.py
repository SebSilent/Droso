def find_Odd_Pair(A,N) : 
    oddPair = 0
    for i in range(0,N) :  
        for j in range(i+1,N) :  
            if ((A[i] ^ A[j]) % 2 != 0):  
                oddPair+=1  
    return oddPair  


assert get_Inv_Count([1,20,6,4,5]) == 5
assert get_Inv_Count([1,2,1]) == 1
assert get_Inv_Count([1,2,5,6,1]) == 3