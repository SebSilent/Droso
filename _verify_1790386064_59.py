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
def sum_average(number):
 total = 0
 for value in range(1, number + 1):
    total = total + value
 average = total / number
 return (total,average)
def min_of_three(*a):
    return sum_average(median_numbers(*a))



assert min_of_three(10,20,0)==0
assert min_of_three(19,15,18)==15
assert min_of_three(-10,-20,-30)==-30