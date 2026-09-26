import math

def remove_all_spaces(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert remove_all_spaces('python  program')==('pythonprogram')
assert remove_all_spaces('python   programming    language')==('pythonprogramminglanguage')
assert remove_all_spaces('python                     program')==('pythonprogram')
assert remove_all_spaces('   python                     program')=='pythonprogram'