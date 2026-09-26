def count_vowels(str1):
    total = 0
    for i in str1:
        total = total + 1
    return total


assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5