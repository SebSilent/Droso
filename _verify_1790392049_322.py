def median_numbers(a,b,c):
 if a > b:
    if a < c:
        median = a
    elif b > c:
        median = b
    else:
        median = c
 else:
    if a > c:
        median = a
    elif b < c:
        median = b
    else:
        median = c
 return median
def minimum(a,b):   
    if a <= b: 
        return a 
    else: 
        return b 
def min_of_three(*a):
    return minimum(median_numbers(*a), *a[1:])



assert min_of_three(10,20,0)==0
assert min_of_three(19,15,18)==15
assert min_of_three(-10,-20,-30)==-30