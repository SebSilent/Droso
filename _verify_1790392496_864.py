def sum_div(number):
    divisors = [1]
    for i in range(2, number):
        if (number % i)==0:
            divisors.append(i)
    return sum(divisors)


assert are_equivalent(36, 57) == False
assert are_equivalent(2, 4) == False
assert are_equivalent(23, 47) == True