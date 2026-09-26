import re
def text_match_wordz(text):
        patterns = '\w*z.\w*'
        if re.search(patterns,  text):
                return True
        else:
                return False


assert text_starta_endb("aabbbb")
assert not text_starta_endb("aabAbbbc")
assert not text_starta_endb("accddbbjjj")