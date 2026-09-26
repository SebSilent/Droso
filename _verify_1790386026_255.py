def multiply_int(x, y):
    if y < 0:
        return -multiply_int(x, -y)
    elif y == 0:
        return 0
    elif y == 1:
        return x
    else:
        return x + multiply_int(x, y - 1)
def sum_div(number):
    divisors = [1]
    for i in range(2, number):
        if (number % i)==0:
            divisors.append(i)
    return sum(divisors)
def are_equivalent(*a):
    return sum_div(multiply_int(*a))



assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True