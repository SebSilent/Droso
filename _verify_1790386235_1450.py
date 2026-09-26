def remove_all_spaces(str1):
    str2 = ''
    for i in range(1, len(str1) + 1):
        if i % 2 == 0:
            str2 = str2 + str1[i - 1]
    return str2


assert remove_all_spaces('python  program')==('pythonprogram')
assert remove_all_spaces('python   programming    language')==('pythonprogramminglanguage')
assert remove_all_spaces('python                     program')==('pythonprogram')
assert remove_all_spaces('   python                     program')=='pythonprogram'