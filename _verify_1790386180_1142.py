from operator import itemgetter
from operator import itemgetter

def sample_nam(test_list):
    res = min(test_list, key=itemgetter(1))[0]
    return res


assert sample_nam(['sally', 'Dylan', 'rebecca', 'Diana', 'Joanne', 'keith'])==16
assert sample_nam(["php", "res", "Python", "abcd", "Java", "aaa"])==10
assert sample_nam(["abcd", "Python", "abba", "aba"])==6