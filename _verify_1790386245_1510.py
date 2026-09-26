def max_run_uppercase(*a):
    return min(a[0])



assert max_run_uppercase('GeMKSForGERksISBESt') == 5
assert max_run_uppercase('PrECIOusMOVemENTSYT') == 6
assert max_run_uppercase('GooGLEFluTTER') == 4