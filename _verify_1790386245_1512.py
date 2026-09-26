def max_val(listval):
     max_val = max(i for i in listval if isinstance(i, int)) 
     return(max_val)


assert max_run_uppercase('GeMKSForGERksISBESt') == 5
assert max_run_uppercase('PrECIOusMOVemENTSYT') == 6
assert max_run_uppercase('GooGLEFluTTER') == 4