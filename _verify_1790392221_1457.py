def remove_all_spaces(*a):
    return [x for x in a[0] if x]



assert remove_all_spaces('python  program')==('pythonprogram')
assert remove_all_spaces('python   programming    language')==('pythonprogramminglanguage')
assert remove_all_spaces('python                     program')==('pythonprogram')
assert remove_all_spaces('   python                     program')=='pythonprogram'