def find_Odd_Pair(A,N) : 
    oddPair = 0
    for i in range(0,N) :  
        for j in range(i+1,N) :  
            if ((A[i] ^ A[j]) % 2 != 0):  
                oddPair+=1  
    return oddPair  


assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12