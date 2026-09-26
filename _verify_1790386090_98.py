def count_Primes_nums(num):    
    rev_num = 0
    while (num > 0):  
        rev_num = (rev_num * 10 + num % 10) 
        num = num // 10  
    return rev_num  
def check(n):    
    return (2 * rev(n) == n + 1)  


assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25