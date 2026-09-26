import re
import re

def first_repeated_char(text):
    for m in re.finditer('\\w+ly', text):
        return '%d-%d: %s' % (m.start(), m.end(), m.group(0))


assert first_repeated_char("abcabc") == "a"
assert first_repeated_char("abc") == None
assert first_repeated_char("123123") == "1"