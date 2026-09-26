def reverse_words(test_str):
    res = ''
    dig = ''
    for ele in test_str:
        if ele.isdigit():
            dig += ele
        else:
            res += ele
    res += dig
    return res


assert reverse_words("python program")==("program python")
assert reverse_words("java language")==("language java")
assert reverse_words("indian man")==("man indian")