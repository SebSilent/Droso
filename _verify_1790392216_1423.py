import re
def text_match_one(text):
        patterns = 'ab+?'
        if re.search(patterns,  text):
                return True
        else:
                return False



assert text_starta_endb("aabbbb")
assert not text_starta_endb("aabAbbbc")
assert not text_starta_endb("accddbbjjj")