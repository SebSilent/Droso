def cube_Sum(number):
    total = 0
    for value in range(1, number + 1):
        total = total + value
    average = total / number
    return (total, average)


assert cube_Sum(2) == 72
assert cube_Sum(3) == 288
assert cube_Sum(4) == 800