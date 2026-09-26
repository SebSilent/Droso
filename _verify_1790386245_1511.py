def max_run_uppercase(*a):
    return [x for x in a[0] if x % 2 == 1]



assert max_run_uppercase('GeMKSForGERksISBESt') == 5
assert max_run_uppercase('PrECIOusMOVemENTSYT') == 6
assert max_run_uppercase('GooGLEFluTTER') == 4