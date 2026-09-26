def cube_Sum(n):  
    sum = 0
    for i in range(1, n + 1): 
        sum += i * i * i  
    return round(sum / n, 6) 


assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800