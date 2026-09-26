import re
import re

def remove_all_spaces(items):
    for item in items:
        return re.sub(' ?\\([^)]+\\)', '', item)


assert remove_all_spaces('python  program')==('pythonprogram')
assert remove_all_spaces('python   programming    language')==('pythonprogramminglanguage')
assert remove_all_spaces('python                     program')==('pythonprogram')
assert remove_all_spaces('   python                     program')=='pythonprogram'