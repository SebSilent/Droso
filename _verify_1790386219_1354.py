def count_vowels(*a):
    return sum(1 for x in a[0] if x == a[1])



assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5