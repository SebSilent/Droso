def remove_whitespaces(str1):
    str2 = ''
    for i in range(1, len(str1) + 1):
        if i % 2 == 0:
            str2 = str2 + str1[i - 1]
    return str2


assert remove_whitespaces(' Google    Flutter ') == 'GoogleFlutter'
assert remove_whitespaces(' Google    Dart ') == 'GoogleDart'
assert remove_whitespaces(' iOS    Swift ') == 'iOSSwift'