def count_divisors(s):
    s = s.split(' ')
    for word in s:
        if len(word) % 2 != 0:
            return True
        else:
            return False


assert count_divisors(10)
assert not count_divisors(100)
assert count_divisors(125)