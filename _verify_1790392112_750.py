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
def hexagonal_num(n): 
	return n*(2*n - 1) 
def parabola_directrix(*a):
    return hexagonal_num(median_numbers(*a))



assert parabola_directrix(5,3,2)==-198
assert parabola_directrix(9,8,4)==-2336
assert parabola_directrix(2,4,6)==-130