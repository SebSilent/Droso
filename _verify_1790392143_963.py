def sum(a,b): 
    sum = 0
    for i in range (1,min(a,b)): 
        if (a % i == 0 and b % i == 0): 
            sum += i 
    return sum
def pair_xor_Sum(arr,n) : 
    ans = 0 
    for i in range(0,n) :    
        for j in range(i + 1,n) :   
            ans = ans + (arr[i] ^ arr[j])          
    return ans 
def perfect_squares(*a):
    return pair_xor_Sum(sum(*a), *a[1:])



assert perfect_squares(1,30)==[1, 4, 9, 16, 25]
assert perfect_squares(50,100)==[64, 81, 100]
assert perfect_squares(100,200)==[100, 121, 144, 169, 196]