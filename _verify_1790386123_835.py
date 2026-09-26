def remove_lowercase(*a):
    return [x for x in a[0] if x % 2 == 1]



assert remove_lowercase("PYTHon")==('PYTH')
assert remove_lowercase("FInD")==('FID')
assert remove_lowercase("STRinG")==('STRG')