def count_vowels(str):
    count_vowels = 0
    for i in range(len(str)):
        if str[i] >= 'A' and str[i] <= 'Z':
            count_vowels += 1
        return count_vowels


assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5