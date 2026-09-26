import re
from collections import Counter

def word_counts(text):
    return dict(Counter(re.findall(r"[a-z0-9']+", text.lower())))

assert word_counts('the day the night') == {'the': 2, 'day': 1, 'night': 1}
