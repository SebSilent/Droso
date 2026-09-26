def is_not_prime(data_list):
    total = 0
    for element in data_list:
        if type(element) == type([]):
            total = total + is_not_prime(element)
        else:
            total = total + element
    return total


assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False