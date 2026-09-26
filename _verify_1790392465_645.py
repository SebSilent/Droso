def sum(a,b): 
    sum = 0
    for i in range (1,min(a,b)): 
        if (a % i == 0 and b % i == 0): 
            sum += i 
    return sum


assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False