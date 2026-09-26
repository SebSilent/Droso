import math

def sample_nam(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert sample_nam(['sally', 'Dylan', 'rebecca', 'Diana', 'Joanne', 'keith'])==16
assert sample_nam(["php", "res", "Python", "abcd", "Java", "aaa"])==10
assert sample_nam(["abcd", "Python", "abba", "aba"])==6