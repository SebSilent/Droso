def remove_lowercase(str1):
    str2 = ''
    for i in range(1, len(str1) + 1):
        if i % 2 == 0:
            str2 = str2 + str1[i - 1]
    return str2


assert remove_lowercase("PYTHon")==('PYTH')
assert remove_lowercase("FInD")==('FID')
assert remove_lowercase("STRinG")==('STRG')