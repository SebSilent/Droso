def string_to_tuple(str1):
    result = tuple(x for x in str1 if not x.isspace()) 
    return result


assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5