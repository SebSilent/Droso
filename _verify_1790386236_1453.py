import re
import re

def remove_all_spaces(ip):
    string = re.sub('\\.[0]*', '.', ip)
    return string


assert remove_all_spaces('python  program')==('pythonprogram')
assert remove_all_spaces('python   programming    language')==('pythonprogramminglanguage')
assert remove_all_spaces('python                     program')==('pythonprogram')
assert remove_all_spaces('   python                     program')=='pythonprogram'