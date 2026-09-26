import re
import re

def text_match_zero_one(text):
    patterns = 'ab+?'
    if re.search(patterns, text):
        return True
    else:
        return False


assert text_match_zero_one("ac")==False
assert text_match_zero_one("dc")==False
assert text_match_zero_one("abbbba")==True
assert text_match_zero_one("dsabbbba")==True
assert text_match_zero_one("asbbbba")==False
assert text_match_zero_one("abaaa")==True