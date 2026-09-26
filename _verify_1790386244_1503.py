def max_run_uppercase(*a):
    m = a[0][0]
    for x in a[0]:
        if x > m:
            m = x
    return m



assert max_run_uppercase('GeMKSForGERksISBESt') == 5
assert max_run_uppercase('PrECIOusMOVemENTSYT') == 6
assert max_run_uppercase('GooGLEFluTTER') == 4