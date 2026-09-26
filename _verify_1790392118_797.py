def remove_whitespaces(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert remove_whitespaces(' Google    Flutter ') == 'GoogleFlutter'
assert remove_whitespaces(' Google    Dart ') == 'GoogleDart'
assert remove_whitespaces(' iOS    Swift ') == 'iOSSwift'