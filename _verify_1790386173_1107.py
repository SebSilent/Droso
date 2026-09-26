def replace_spaces(test_str):
    res = ''
    dig = ''
    for ele in test_str:
        if ele.isdigit():
            dig += ele
        else:
            res += ele
    res += dig
    return res


assert replace_spaces("My Name is Dawood") == 'My%20Name%20is%20Dawood'
assert replace_spaces("I am a Programmer") == 'I%20am%20a%20Programmer'
assert replace_spaces("I love Coding") == 'I%20love%20Coding'