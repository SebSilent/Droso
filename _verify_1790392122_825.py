def remove_lowercase(test_tup):
    res = tuple()
    for count, ele in enumerate(test_tup):
        if not isinstance(ele, tuple):
            res = res + (ele,)
    return res


assert remove_lowercase("PYTHon")==('PYTH')
assert remove_lowercase("FInD")==('FID')
assert remove_lowercase("STRinG")==('STRG')