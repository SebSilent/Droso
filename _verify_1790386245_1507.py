def max_run_uppercase(*a):
    return ' '.join(w.capitalize() for w in a[0].split())



assert max_run_uppercase('GeMKSForGERksISBESt') == 5
assert max_run_uppercase('PrECIOusMOVemENTSYT') == 6
assert max_run_uppercase('GooGLEFluTTER') == 4