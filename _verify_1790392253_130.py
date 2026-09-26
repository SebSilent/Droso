def power(base, power):
    return sum([int(i) for i in str(pow(base, power))])


assert power(3,4) == 81
assert power(2,3) == 8
assert power(5,5) == 3125