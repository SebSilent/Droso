def sum_average(number):
 total = 0
 for value in range(1, number + 1):
    total = total + value
 average = total / number
 return (total,average)


assert min_of_three(10,20,0)==0
assert min_of_three(19,15,18)==15
assert min_of_three(-10,-20,-30)==-30