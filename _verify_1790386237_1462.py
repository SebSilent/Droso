import re
def remove_parenthesis(items):
 for item in items:
    return (re.sub(r" ?\([^)]+\)", "", item))


assert remove_all_spaces('python  program')==('pythonprogram')
assert remove_all_spaces('python   programming    language')==('pythonprogramminglanguage')
assert remove_all_spaces('python                     program')==('pythonprogram')
assert remove_all_spaces('   python                     program')=='pythonprogram'