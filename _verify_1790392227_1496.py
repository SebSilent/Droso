def max_run_uppercase(str1):
    result = tuple((x for x in str1 if not x.isspace()))
    return result


assert max_run_uppercase('GeMKSForGERksISBESt') == 5
assert max_run_uppercase('PrECIOusMOVemENTSYT') == 6
assert max_run_uppercase('GooGLEFluTTER') == 4