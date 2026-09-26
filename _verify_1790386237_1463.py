def remove_all_spaces(*a):
    return min(a[0])



assert remove_all_spaces('python  program')==('pythonprogram')
assert remove_all_spaces('python   programming    language')==('pythonprogramminglanguage')
assert remove_all_spaces('python                     program')==('pythonprogram')
assert remove_all_spaces('   python                     program')=='pythonprogram'