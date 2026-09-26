import re
import re

def text_lowercase_underscore(str1):
    return re.sub('(\\w)([A-Z])', '\\1 \\2', str1)


assert text_lowercase_underscore("aab_cbbbc")==(True)
assert text_lowercase_underscore("aab_Abbbc")==(False)
assert text_lowercase_underscore("Aaab_abbbc")==(False)