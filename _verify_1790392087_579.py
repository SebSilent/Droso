import re
import re

def start_withp(str1):
    return re.sub('(\\w)([A-Z])', '\\1 \\2', str1)


assert start_withp(["Python PHP", "Java JavaScript", "c c++"])==('Python', 'PHP')
assert start_withp(["Python Programming","Java Programming"])==('Python','Programming')
assert start_withp(["Pqrst Pqr","qrstuv"])==('Pqrst','Pqr')