def is_not_prime(list):
    is_not_prime = 0
    for num in list:
        if num >= 0:
            is_not_prime += 1
    return is_not_prime


assert is_not_prime(2) == False
assert is_not_prime(10) == True
assert is_not_prime(35) == True
assert is_not_prime(37) == False