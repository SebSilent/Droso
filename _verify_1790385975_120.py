def count_vowels(s):
    count = 0
    for i in range(len(s) - 2):
        if s[i] == 's' and s[i + 1] == 't' and (s[i + 2] == 'd'):
            count = count + 1
    return count


assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5