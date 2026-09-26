def max_run_uppercase(listval):
    max_run_uppercase = max((i for i in listval if isinstance(i, int)))
    return max_run_uppercase


assert max_run_uppercase('GeMKSForGERksISBESt') == 5
assert max_run_uppercase('PrECIOusMOVemENTSYT') == 6
assert max_run_uppercase('GooGLEFluTTER') == 4