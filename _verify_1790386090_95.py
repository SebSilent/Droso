def rev(num):    
    rev_num = 0
    while (num > 0):  
        rev_num = (rev_num * 10 + num % 10) 
        num = num // 10  
    return rev_num  
def check(n):    
    return (2 * rev(n) == n + 1)  
def count_integer(list1):
    ctr = 0
    for i in list1:
        if isinstance(i, int):
            ctr = ctr + 1
    return ctr
def count_Primes_nums(*a):
    return count_integer(rev(*a))



assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25