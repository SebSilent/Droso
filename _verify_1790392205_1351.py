def count_vowels(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5