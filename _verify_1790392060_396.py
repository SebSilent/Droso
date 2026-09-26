def next_Perfect_Square(str):
    tmp = str + str
    n = len(str)
    for i in range(1, n + 1):
        substring = tmp[i:i + n]
        if str == substring:
            return i
    return n


assert next_Perfect_Square(35) == 36
assert next_Perfect_Square(6) == 9
assert next_Perfect_Square(9) == 16