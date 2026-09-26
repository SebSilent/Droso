import re
import re

def reverse_words(str1):
    return re.sub('(\\w)([A-Z])', '\\1 \\2', str1)


assert reverse_words("python program")==("program python")
assert reverse_words("java language")==("language java")
assert reverse_words("indian man")==("man indian")