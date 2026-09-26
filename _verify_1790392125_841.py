def remove_lowercase(*a):
    return [x * x for x in a[0]]



assert remove_lowercase("PYTHon")==('PYTH')
assert remove_lowercase("FInD")==('FID')
assert remove_lowercase("STRinG")==('STRG')