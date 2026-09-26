def sample_nam(*a):
    t = 0
    for x in a[0]:
        t += 1
    return t



assert sample_nam(['sally', 'Dylan', 'rebecca', 'Diana', 'Joanne', 'keith'])==16
assert sample_nam(["php", "res", "Python", "abcd", "Java", "aaa"])==10
assert sample_nam(["abcd", "Python", "abba", "aba"])==6